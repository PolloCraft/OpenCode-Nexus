use axum::{
    middleware::{self, Next},
    routing::{get, post},
    Router,
};
use std::net::SocketAddr;
use std::sync::Arc;
use tokio::sync::Mutex;
use tracing::info;

use crate::config::ProxyConfig;
use crate::dashboard::{
    handle_api_clear_all_data, handle_api_clear_cache, handle_api_config,
    handle_api_desktop_status, handle_api_logs, handle_api_models,
    handle_api_network_backup, handle_api_network_restore, handle_api_network_status,
    handle_api_opencode_folders, handle_api_reset_ip, handle_api_restore_desktop,
    handle_api_restore_ip, handle_api_setup_desktop, handle_api_status, handle_api_sessions,
    serve_dashboard,
};
use crate::proxy::handlers::{
    handle_desktop_anthropic, handle_desktop_openai, handle_desktop_v1_proxy,
    handle_model_detail, handle_models,
};
use crate::sessions::SessionGuard;
use crate::warp::WarpResolver;

pub struct ProxyState {
    pub config: ProxyConfig,
    pub client: reqwest::Client,
    pub warp_resolver: Arc<WarpResolver>,
    pub session_guard: Arc<SessionGuard>,
}

pub struct AppState {
    pub proxy: ProxyState,
    pub logs: Vec<String>,
}

async fn log_requests(
    request: axum::http::Request<axum::body::Body>,
    next: Next,
) -> axum::response::Response {
    let method = request.method().clone();
    let uri = request.uri().clone();

    let path = uri.path();
    if !path.starts_with("/api/") && path != "/" && !path.starts_with("/assets") {
        info!("→ {} {}", method, uri);
    }

    let response = next.run(request).await;

    if path.starts_with("/api/") {
        info!("← {} {} {}", method, uri, response.status());
    }

    response
}

pub fn build_client() -> reqwest::Result<reqwest::Client> {
    reqwest::Client::builder()
        .connect_timeout(std::time::Duration::from_secs(10))
        .read_timeout(std::time::Duration::from_secs(300))
        .build()
}

pub async fn start_proxy_server(config: ProxyConfig) -> anyhow::Result<()> {
    let client = build_client()?;

    let warp_resolver = WarpResolver::new(config.max_retries, config.warp_reset_delay_ms);

    let session_guard = Arc::new(SessionGuard::new());
    session_guard.init().await;

    let state = Arc::new(Mutex::new(AppState {
        proxy: ProxyState {
            config: config.clone(),
            client,
            warp_resolver,
            session_guard,
        },
        logs: Vec::new(),
    }));

    let app = Router::new()
        .route("/", get(serve_dashboard))
        .route("/dashboard", get(serve_dashboard))
        .route("/api/status", get(handle_api_status))
        .route("/api/models", get(handle_api_models))
        .route("/api/logs", get(handle_api_logs))
        .route("/api/config", get(handle_api_config))
        .route("/api/reset-ip", post(handle_api_reset_ip))
        .route("/api/restore-ip", post(handle_api_restore_ip))
        .route("/api/network/backup", post(handle_api_network_backup))
        .route("/api/network/status", get(handle_api_network_status))
        .route("/api/network/restore", post(handle_api_network_restore))
        .route("/api/desktop-status", get(handle_api_desktop_status))
        .route("/api/setup-desktop", post(handle_api_setup_desktop))
        .route("/api/restore-desktop", post(handle_api_restore_desktop))
        .route("/api/sessions", get(handle_api_sessions))
        .route("/api/opencode-folders", get(handle_api_opencode_folders))
        .route("/api/clear-cache", post(handle_api_clear_cache))
        .route("/api/clear-all-data", post(handle_api_clear_all_data))
        .route("/v1/models", get(handle_models))
        .route("/v1/models/{model_id}", get(handle_model_detail))
        .route("/v1/messages", post(handle_desktop_anthropic))
        .route("/v1/chat/completions", post(handle_desktop_openai))
        .route("/v1/responses", post(handle_desktop_openai))
        .route("/v1/embeddings", post(handle_desktop_v1_proxy))
        .route("/health", get(|| async { "OK" }))
        .layer(middleware::from_fn(log_requests))
        .with_state(state);

    let addr: SocketAddr = config
        .listen_addr
        .parse()
        .unwrap_or_else(|_| "127.0.0.1:8080".parse().unwrap());

    info!("Starting proxy server on {}", addr);
    info!("OpenCode Zen upstream: {}", config.opencode_base_url);
    info!("Dashboard: http://{}", addr);

    let listener = tokio::net::TcpListener::bind(&addr).await?;
    info!("Proxy server listening on http://{}", addr);

    axum::serve(listener, app).await?;

    Ok(())
}
