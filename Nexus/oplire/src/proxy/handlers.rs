use axum::{
    body::Body,
    extract::State,
    http::{HeaderMap, HeaderValue, StatusCode},
    response::{IntoResponse, Response},
    Json,
};
use bytes::Bytes;
use futures::StreamExt;
use serde_json::Value;
use std::sync::Arc;
use std::time::Duration;
use tokio::sync::Mutex;
use tracing::{error, info, warn};

use crate::config::ProxyConfig;
use crate::proxy::server::AppState;
use crate::sessions::TokenUsage;
use crate::transform::{
    anthropic_to_opencode_request, opencode_response_to_anthropic,
    opencode_stream_to_anthropic,
};

const ANTHROPIC_BASE: &str = "https://api.anthropic.com";
const OPENAI_BASE: &str = "https://api.openai.com";

// User-Agents para rotacion (anti-deteccion)
const USER_AGENTS: &[&str] = &[
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:133.0) Gecko/20100101 Firefox/133.0",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
];

fn get_random_user_agent() -> &'static str {
    use std::time::{SystemTime, UNIX_EPOCH};
    let nanos = SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .unwrap_or_default()
        .subsec_nanos();
    let index = (nanos as usize) % USER_AGENTS.len();
    USER_AGENTS[index]
}

#[allow(dead_code)]
fn random_delay_ms(min_ms: u64, max_ms: u64) -> Duration {
    use std::time::{SystemTime, UNIX_EPOCH};
    let nanos = SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .unwrap_or_default()
        .subsec_nanos();
    let range = max_ms - min_ms;
    let delay = min_ms + (nanos as u64 % range);
    Duration::from_millis(delay)
}

fn create_shared_client() -> reqwest::Client {
    reqwest::Client::builder()
        .connect_timeout(Duration::from_secs(10))
        .read_timeout(Duration::from_secs(300))
        .pool_max_idle_per_host(10)
        .tcp_keepalive(Duration::from_secs(60))
        .user_agent(get_random_user_agent())
        .build()
        .unwrap_or_default()
}

pub async fn handle_models(State(state): State<Arc<Mutex<AppState>>>) -> impl IntoResponse {
    let (base_url, api_key) = {
        let s = state.lock().await;
        (
            s.proxy.config.opencode_base_url.clone(),
            s.proxy.config.opencode_api_key.clone(),
        )
    };

    let models_url = format!("{}/v1/models", base_url.trim_end_matches('/'));

    let client = create_shared_client();
    let mut request = client.get(&models_url).header("Accept", "application/json");

    if let Some(key) = &api_key {
        request = request.header("Authorization", format!("Bearer {}", key));
    }

    match request.send().await {
        Ok(resp) if resp.status().is_success() => {
            match resp.json::<Value>().await {
                Ok(upstream_models) => {
                    let transformed = transform_models_to_anthropic(&upstream_models);
                    (StatusCode::OK, Json(transformed))
                }
                Err(e) => {
                    error!("Failed to parse models response: {}", e);
                    (StatusCode::OK, Json(ProxyConfig::models_response()))
                }
            }
        }
        Ok(resp) => {
            warn!("Upstream /v1/models returned status: {}", resp.status());
            (StatusCode::OK, Json(ProxyConfig::models_response()))
        }
        Err(e) => {
            warn!("Failed to fetch models from upstream: {}", e);
            (StatusCode::OK, Json(ProxyConfig::models_response()))
        }
    }
}

fn transform_models_to_anthropic(upstream: &Value) -> Value {
    let data = upstream.get("data").and_then(|v| v.as_array());

    let models: Vec<Value> = match data {
        Some(models_array) => models_array
            .iter()
            .filter_map(|m| {
                let id = m.get("id").and_then(|v| v.as_str()).unwrap_or("");
                if id.is_empty() {
                    return None;
                }

                let display_name = match m.get("name").or_else(|| m.get("display_name")).and_then(|v| v.as_str()) {
                    Some(name) => name.to_string(),
                    None => id.replace('-', " ")
                        .split_whitespace()
                        .map(|w| {
                            let mut chars = w.chars();
                            match chars.next() {
                                None => String::new(),
                                Some(c) => {
                                    let upper = c.to_uppercase().collect::<String>();
                                    format!("{}{}", upper, chars.as_str())
                                }
                            }
                        })
                        .collect::<Vec<_>>()
                        .join(" "),
                };

                let context_window = m
                    .get("context_window")
                    .and_then(|v| v.as_u64())
                    .or_else(|| m.get("max_tokens").and_then(|v| v.as_u64()))
                    .unwrap_or(128_000);

                let pricing_input = m
                    .get("input_price")
                    .and_then(|v| v.as_f64())
                    .unwrap_or(0.0);
                let pricing_output = m
                    .get("output_price")
                    .and_then(|v| v.as_f64())
                    .unwrap_or(0.0);

                let mut model = serde_json::Map::new();
                model.insert("id".to_string(), Value::String(id.to_string()));
                model.insert("name".to_string(), Value::String(display_name.clone()));
                model.insert("type".to_string(), Value::String("model".to_string()));
                model.insert("display_name".to_string(), Value::String(display_name));
                model.insert("context_window".to_string(), Value::Number(serde_json::Number::from(context_window)));
                model.insert("input_price".to_string(), Value::Number(serde_json::Number::from_f64(pricing_input).unwrap_or(serde_json::Number::from_f64(0.0).unwrap())));
                model.insert("output_price".to_string(), Value::Number(serde_json::Number::from_f64(pricing_output).unwrap_or(serde_json::Number::from_f64(0.0).unwrap())));

                if let Some(created) = m.get("created") {
                    model.insert("created".to_string(), created.clone());
                }
                if let Some(owned_by) = m.get("owned_by") {
                    model.insert("owned_by".to_string(), owned_by.clone());
                }
                if let Some(arch) = m.get("architecture") {
                    model.insert("architecture".to_string(), arch.clone());
                }

                Some(Value::Object(model))
            })
            .collect(),
        None => {
            ProxyConfig::free_models()
                .iter()
                .map(|m| {
                    serde_json::json!({
                        "id": m.id,
                        "name": m.display_name,
                        "type": "model",
                        "display_name": m.display_name,
                        "context_window": 128000,
                        "input_price": 0.0,
                        "output_price": 0.0
                    })
                })
                .collect()
        }
    };

    serde_json::json!({
        "data": models,
        "has_more": false,
        "first_id": models.first().and_then(|m| m.get("id").and_then(|v| v.as_str())).unwrap_or(""),
        "last_id": models.last().and_then(|m| m.get("id").and_then(|v| v.as_str())).unwrap_or("")
    })
}

pub async fn handle_model_detail(
    State(state): State<Arc<Mutex<AppState>>>,
    axum::extract::Path(model_id): axum::extract::Path<String>,
) -> impl IntoResponse {
    let (base_url, api_key) = {
        let s = state.lock().await;
        (
            s.proxy.config.opencode_base_url.clone(),
            s.proxy.config.opencode_api_key.clone(),
        )
    };

    let model_url = format!("{}/v1/models/{}", base_url.trim_end_matches('/'), model_id);

    let client = create_shared_client();
    let mut request = client.get(&model_url).header("Accept", "application/json");

    if let Some(key) = &api_key {
        request = request.header("Authorization", format!("Bearer {}", key));
    }

    match request.send().await {
        Ok(resp) if resp.status().is_success() => {
            match resp.json::<Value>().await {
                Ok(model) => {
                    let mut transformed = serde_json::Map::new();
                    if let Some(id) = model.get("id").and_then(|v| v.as_str()) {
                        transformed.insert("id".to_string(), Value::String(id.to_string()));
                    }
                    if let Some(name) = model.get("name").and_then(|v| v.as_str()) {
                        transformed.insert("name".to_string(), Value::String(name.to_string()));
                        transformed.insert("display_name".to_string(), Value::String(name.to_string()));
                    }
                    transformed.insert("type".to_string(), Value::String("model".to_string()));

                    (StatusCode::OK, Json(Value::Object(transformed))).into_response()
                }
                Err(e) => {
                    error!("Failed to parse model detail: {}", e);
                    StatusCode::NOT_FOUND.into_response()
                }
            }
        }
        _ => StatusCode::NOT_FOUND.into_response(),
    }
}

pub async fn handle_messages(
    State(state): State<Arc<Mutex<AppState>>>,
    _headers: HeaderMap,
    body: Bytes,
) -> Response {
    let request_body = match serde_json::from_slice::<Value>(&body) {
        Ok(v) => v,
        Err(e) => {
            error!("Failed to parse request body: {}", e);
            return error_response(&format!("Invalid JSON: {}", e));
        }
    };

    let is_stream = request_body
        .get("stream")
        .and_then(|v| v.as_bool())
        .unwrap_or(false);

    let model = request_body
        .get("model")
        .and_then(|v| v.as_str())
        .unwrap_or("unknown")
        .to_string();

    let is_anthropic_format = detect_anthropic_format(&request_body);

    let opencode_body = if is_anthropic_format {
        info!("Detected Anthropic format, transforming to OpenAI");
        anthropic_to_opencode_request(&request_body)
    } else {
        info!("Detected OpenAI format, forwarding directly");
        request_body.clone()
    };

    let (base_url, api_key, warp_resolver, session_guard) = {
        let s = state.lock().await;
        (
            s.proxy.config.opencode_base_url.clone(),
            s.proxy.config.opencode_api_key.clone(),
            s.proxy.warp_resolver.clone(),
            s.proxy.session_guard.clone(),
        )
    };

    let mut retry_count = 0;
    let mut client = create_shared_client();

    loop {
        let result = if is_stream {
            forward_streaming_with_client(&client, &base_url, &api_key, &opencode_body, &model).await
        } else {
            forward_non_streaming_with_client(&client, &base_url, &api_key, &opencode_body, &model).await
        };

        match result {
            Ok(response) => return response,
            Err(ProxyError::RateLimited) => {
                retry_count += 1;
                if retry_count > warp_resolver.max_retries {
                    record_limit_reached(
                        &session_guard,
                        &opencode_body,
                        "Rate limit exceeded after WARP resets (429)",
                        StatusCode::TOO_MANY_REQUESTS,
                    ).await;
                    return error_response("Rate limit exceeded after WARP resets");
                }

                info!(
                    "429 received, attempting WARP reset (attempt {}/{})",
                    retry_count, warp_resolver.max_retries
                );

                if !warp_resolver.handle_429(retry_count - 1).await {
                    record_limit_reached(
                        &session_guard,
                        &opencode_body,
                        "WARP reset failed, rate limit persistent",
                        StatusCode::TOO_MANY_REQUESTS,
                    ).await;
                    return error_response("WARP reset failed, rate limit still active");
                }
                client = create_shared_client();
                {
                    let mut s = state.lock().await;
                    s.proxy.client = client.clone();
                }
                info!("Rebuilt HTTP client pool after WARP reset");
            }
            Err(ProxyError::TokenLimitReached(msg)) => {
                warn!("Token limit detected: {}", msg);
                record_limit_reached(
                    &session_guard,
                    &opencode_body,
                    &msg,
                    StatusCode::BAD_REQUEST,
                ).await;
                return error_response(&msg);
            }
            Err(ProxyError::RequestFailed(msg)) => {
                error!("Upstream request failed: {}", msg);

                if is_rate_limit_or_quota_error(StatusCode::from_u16(0).unwrap_or(StatusCode::OK), &msg) {
                    record_limit_reached(
                        &session_guard,
                        &opencode_body,
                        &format!("Upstream error: {}", msg),
                        StatusCode::BAD_REQUEST,
                    ).await;
                }

                return error_response(&format!("Upstream error: {}", msg));
            }
        }
    }
}

async fn forward_streaming_with_client(
    client: &reqwest::Client,
    base_url: &str,
    api_key: &Option<String>,
    body: &Value,
    model: &str,
) -> Result<Response, ProxyError> {
    let url = format!("{}/v1/chat/completions", base_url.trim_end_matches('/'));

    let mut request = client
        .post(&url)
        .header("Content-Type", "application/json")
        .header("Accept", "text/event-stream")
        .json(body);

    if let Some(key) = api_key {
        request = request.header("Authorization", format!("Bearer {}", key));
    }

    let response = request
        .send()
        .await
        .map_err(|e| ProxyError::RequestFailed(e.to_string()))?;

    if response.status() == 429 {
        return Err(ProxyError::RateLimited);
    }

    if !response.status().is_success() {
        let status = response.status();
        let body_text = response
            .text()
            .await
            .unwrap_or_else(|_| "Unknown error".to_string());

        if is_token_limit_error(&body_text) {
            return Err(ProxyError::TokenLimitReached(format!(
                "Token limit reached: {}",
                body_text
            )));
        }

        if is_rate_limit_or_quota_error(status, &body_text) {
            return Err(ProxyError::RateLimited);
        }

        return Err(ProxyError::RequestFailed(format!(
            "Upstream {} : {}",
            status, body_text
        )));
    }

    let model_owned = model.to_string();
    let stream = response
        .bytes_stream()
        .map(move |chunk| {
            let chunk = chunk.map_err(std::io::Error::other)?;
            let lines = String::from_utf8_lossy(&chunk);
            let mut output = String::new();

            for line in lines.lines() {
                if let Some(transformed) = opencode_stream_to_anthropic(line, &model_owned) {
                    output.push_str(&transformed);
                }
            }

            if output.is_empty() {
                Ok::<Bytes, std::io::Error>(Bytes::from(lines.into_owned()))
            } else {
                Ok::<Bytes, std::io::Error>(Bytes::from(output))
            }
        });

    let body = Body::from_stream(stream);

    let mut response = Response::new(body);
    *response.status_mut() = StatusCode::OK;
    response.headers_mut().insert(
        "Content-Type",
        HeaderValue::from_static("text/event-stream; charset=utf-8"),
    );
    response.headers_mut().insert(
        "Cache-Control",
        HeaderValue::from_static("no-cache"),
    );
    response
        .headers_mut()
        .insert("Connection", HeaderValue::from_static("keep-alive"));
    response
        .headers_mut()
        .insert("X-Accel-Buffering", HeaderValue::from_static("no"));

    Ok(response)
}

async fn forward_non_streaming_with_client(
    client: &reqwest::Client,
    base_url: &str,
    api_key: &Option<String>,
    body: &Value,
    model: &str,
) -> Result<Response, ProxyError> {
    let url = format!("{}/v1/chat/completions", base_url.trim_end_matches('/'));

    let mut request = client
        .post(&url)
        .header("Content-Type", "application/json")
        .json(body);

    if let Some(key) = api_key {
        request = request.header("Authorization", format!("Bearer {}", key));
    }

    let response = request
        .send()
        .await
        .map_err(|e| ProxyError::RequestFailed(e.to_string()))?;

    if response.status() == 429 {
        return Err(ProxyError::RateLimited);
    }

    if !response.status().is_success() {
        let status = response.status();
        let body_text = response
            .text()
            .await
            .unwrap_or_else(|_| "Unknown error".to_string());

        if is_token_limit_error(&body_text) {
            return Err(ProxyError::TokenLimitReached(format!(
                "Token limit reached: {}",
                body_text
            )));
        }

        if is_rate_limit_or_quota_error(status, &body_text) {
            return Err(ProxyError::RateLimited);
        }

        return Err(ProxyError::RequestFailed(format!(
            "Upstream {} : {}",
            status, body_text
        )));
    }

    let opencode_response = response
        .json::<Value>()
        .await
        .map_err(|e| ProxyError::RequestFailed(e.to_string()))?;

    let anthropic_response = opencode_response_to_anthropic(&opencode_response, model);

    let mut headers = HeaderMap::new();
    headers.insert(
        "Content-Type",
        HeaderValue::from_static("application/json"),
    );
    headers.insert(
        "x-request-id",
        HeaderValue::from_str(&format!(
            "req_{}",
            std::time::SystemTime::now()
                .duration_since(std::time::UNIX_EPOCH)
                .map(|d| d.as_millis())
                .unwrap_or(0)
        ))
        .unwrap_or(HeaderValue::from_static("unknown")),
    );

    Ok((StatusCode::OK, headers, Json(anthropic_response)).into_response())
}

fn error_response(message: &str) -> Response {
    let body = serde_json::json!({
        "error": {
            "message": message,
            "type": "api_error",
            "code": "internal_error"
        }
    });
    (StatusCode::INTERNAL_SERVER_ERROR, Json(body)).into_response()
}

fn detect_anthropic_format(body: &Value) -> bool {
    if body.get("system").is_some() {
        return true;
    }

    if body.get("max_tokens").is_some() && body.get("messages").is_some() {
        if let Some(msgs) = body.get("messages").and_then(|v| v.as_array()) {
            if let Some(first) = msgs.first() {
                if let Some(content) = first.get("content") {
                    if let Some(arr) = content.as_array() {
                        if let Some(block) = arr.first() {
                            if block.get("type").is_some() {
                                return true;
                            }
                        }
                    }
                }
            }
        }
    }

    false
}

#[derive(Debug)]
enum ProxyError {
    RateLimited,
    TokenLimitReached(String),
    RequestFailed(String),
}

fn is_rate_limit_or_quota_error(status: StatusCode, body: &str) -> bool {
    if status.as_u16() == 429 {
        return true;
    }

    let body_lower = body.to_lowercase();

    body_lower.contains("rate limit")
        || body_lower.contains("token limit")
        || body_lower.contains("quota exceeded")
        || body_lower.contains("too many requests")
        || body_lower.contains("limit reached")
        || body_lower.contains("tokens per")
        || body_lower.contains("requests per")
        || body_lower.contains("credits")
        || body_lower.contains("usage limit")
}

fn is_token_limit_error(body: &str) -> bool {
    let body_lower = body.to_lowercase();

    body_lower.contains("token limit")
        || body_lower.contains("tokens per")
        || body_lower.contains("context length")
        || body_lower.contains("maximum context")
        || body_lower.contains("input tokens")
        || body_lower.contains("context window")
}

async fn record_limit_reached(
    session_guard: &crate::sessions::SessionGuard,
    body: &Value,
    reason: &str,
    _status: StatusCode,
) {
    let model = body
        .get("model")
        .and_then(|v| v.as_str())
        .unwrap_or("unknown")
        .to_string();

    let messages = body
        .get("messages")
        .and_then(|v| v.as_array());

    let message_count = messages.map(|m| m.len() as u32).unwrap_or(0);

    let input_tokens = estimate_tokens_from_messages(messages);

    let usage = TokenUsage {
        input_tokens,
        output_tokens: 0,
        total_tokens: input_tokens,
    };

    let sessions_dir_path = session_guard.get_sessions_dir_path();
    let sessions_dir = std::path::PathBuf::from(sessions_dir_path);

    if let Ok(mut entries) = tokio::fs::read_dir(&sessions_dir).await {
        let mut latest_session: Option<(String, u64)> = None;

        while let Ok(Some(entry)) = entries.next_entry().await {
            if entry.path().extension().and_then(|e| e.to_str()) == Some("json") {
                if let Ok(meta) = tokio::fs::metadata(entry.path()).await {
                    if let Ok(modified) = meta.modified() {
                        if let Ok(dur) = modified.duration_since(std::time::UNIX_EPOCH) {
                            let ts = dur.as_secs();
                            match &latest_session {
                                Some((_, prev_ts)) if ts > *prev_ts => {
                                    latest_session = Some((entry.path().display().to_string(), ts));
                                }
                                None => {
                                    latest_session = Some((entry.path().display().to_string(), ts));
                                }
                                _ => {}
                            }
                        }
                    }
                }
            }
        }

        if let Some((session_path, _)) = latest_session {
            let _ = session_guard
                .mark_session_limit_reached(&session_path, reason, Some(usage))
                .await;
            info!(
                "Recorded token limit reached for session: model={}, messages={}, input_tokens_est={}",
                model, message_count, input_tokens
            );
        }
    }
}

fn estimate_tokens_from_messages(messages: Option<&Vec<Value>>) -> u64 {
    match messages {
        Some(msgs) => {
            let mut total_chars = 0u64;
            for msg in msgs {
                if let Some(content) = msg.get("content") {
                    total_chars += match content {
                        Value::String(s) => s.len() as u64,
                        Value::Array(arr) => arr
                            .iter()
                            .filter_map(|c| c.get("text").and_then(|t| t.as_str()))
                            .map(|t| t.len() as u64)
                            .sum(),
                        _ => 0,
                    };
                }
            }
            total_chars / 4
        }
        None => 0,
    }
}

pub async fn handle_desktop_anthropic(
    State(state): State<Arc<Mutex<AppState>>>,
    headers: HeaderMap,
    body: Bytes,
) -> Response {
    let (warp_resolver, session_guard) = {
        let s = state.lock().await;
        (s.proxy.warp_resolver.clone(), s.proxy.session_guard.clone())
    };

    let client = create_shared_client();
    let url = format!("{}/v1/messages", ANTHROPIC_BASE);

    let mut retry_count = 0;
    loop {
        let mut req_builder = client.post(&url).body(body.clone());

        for (key, value) in headers.iter() {
            if key == "host" || key == "connection" {
                continue;
            }
            req_builder = req_builder.header(key, value);
        }

        req_builder = req_builder.header(
            "anthropic-version",
            headers
                .get("anthropic-version")
                .and_then(|v| v.to_str().ok())
                .unwrap_or("2023-06-01"),
        );

        let response = match req_builder.send().await {
            Ok(r) => r,
            Err(e) => {
                return error_response(&format!("Request failed: {}", e));
            }
        };

        if response.status() == 429 {
            retry_count += 1;
            if retry_count > warp_resolver.max_retries {
                record_limit_reached(
                    &session_guard,
                    &serde_json::from_slice(&body).unwrap_or(serde_json::json!({})),
                    "Desktop Anthropic: Rate limit exceeded after WARP resets",
                    StatusCode::TOO_MANY_REQUESTS,
                ).await;
                return error_response("Rate limit exceeded after WARP resets");
            }
            info!(
                "[Desktop] 429 received, WARP reset (attempt {}/{})",
                retry_count, warp_resolver.max_retries
            );
            if !warp_resolver.handle_429(retry_count - 1).await {
                record_limit_reached(
                    &session_guard,
                    &serde_json::from_slice(&body).unwrap_or(serde_json::json!({})),
                    "Desktop Anthropic: WARP reset failed",
                    StatusCode::TOO_MANY_REQUESTS,
                ).await;
                return error_response("WARP reset failed");
            }
            continue;
        }

        let status = response.status();
        let resp_headers = response.headers().clone();
        let is_stream = resp_headers
            .get("content-type")
            .and_then(|v| v.to_str().ok())
            .map(|v| v.contains("text/event-stream"))
            .unwrap_or(false);

        if is_stream {
            let stream = response
                .bytes_stream()
                .map(|chunk| chunk.map_err(std::io::Error::other));
            let body = Body::from_stream(stream);
            let mut resp = Response::new(body);
            *resp.status_mut() = status;
            for (k, v) in &resp_headers {
                if k != "content-length" {
                    resp.headers_mut().insert(k.clone(), v.clone());
                }
            }
            return resp;
        }

        let resp_body = match response.bytes().await {
            Ok(b) => b,
            Err(e) => {
                return error_response(&format!("Failed to read response: {}", e));
            }
        };

        let resp_text = String::from_utf8_lossy(&resp_body);

        if is_rate_limit_or_quota_error(status, &resp_text) {
            warn!("[Desktop] Rate limit/quota error detected: {}", status);
            if is_token_limit_error(&resp_text) {
                record_limit_reached(
                    &session_guard,
                    &serde_json::from_slice(&body).unwrap_or(serde_json::json!({})),
                    &format!("Token limit: {}", resp_text),
                    status,
                ).await;
            }
        }

        let mut resp = Response::new(Body::from(resp_body));
        *resp.status_mut() = status;
        for (k, v) in &resp_headers {
            if k != "content-length" {
                resp.headers_mut().insert(k.clone(), v.clone());
            }
        }
        return resp;
    }
}

pub async fn handle_desktop_openai(
    State(state): State<Arc<Mutex<AppState>>>,
    axum::extract::OriginalUri(uri): axum::extract::OriginalUri,
    headers: HeaderMap,
    body: Bytes,
) -> Response {
    let (warp_resolver, session_guard) = {
        let s = state.lock().await;
        (s.proxy.warp_resolver.clone(), s.proxy.session_guard.clone())
    };

    let client = create_shared_client();
    let path = uri.path();
    let url = format!("{}{}", OPENAI_BASE, path);

    let mut retry_count = 0;
    loop {
        let mut req_builder = client.post(&url).body(body.clone());

        for (key, value) in headers.iter() {
            if key == "host" || key == "connection" {
                continue;
            }
            req_builder = req_builder.header(key, value);
        }

        let response = match req_builder.send().await {
            Ok(r) => r,
            Err(e) => {
                return error_response(&format!("Request failed: {}", e));
            }
        };

        if response.status() == 429 {
            retry_count += 1;
            if retry_count > warp_resolver.max_retries {
                record_limit_reached(
                    &session_guard,
                    &serde_json::from_slice(&body).unwrap_or(serde_json::json!({})),
                    "Desktop OpenAI: Rate limit exceeded after WARP resets",
                    StatusCode::TOO_MANY_REQUESTS,
                ).await;
                return error_response("Rate limit exceeded after WARP resets");
            }
            info!(
                "[Desktop] 429 received, WARP reset (attempt {}/{})",
                retry_count, warp_resolver.max_retries
            );
            if !warp_resolver.handle_429(retry_count - 1).await {
                record_limit_reached(
                    &session_guard,
                    &serde_json::from_slice(&body).unwrap_or(serde_json::json!({})),
                    "Desktop OpenAI: WARP reset failed",
                    StatusCode::TOO_MANY_REQUESTS,
                ).await;
                return error_response("WARP reset failed");
            }
            continue;
        }

        let status = response.status();
        let resp_headers = response.headers().clone();
        let is_stream = resp_headers
            .get("content-type")
            .and_then(|v| v.to_str().ok())
            .map(|v| v.contains("text/event-stream"))
            .unwrap_or(false);

        if is_stream {
            let stream = response
                .bytes_stream()
                .map(|chunk| chunk.map_err(std::io::Error::other));
            let body = Body::from_stream(stream);
            let mut resp = Response::new(body);
            *resp.status_mut() = status;
            for (k, v) in &resp_headers {
                if k != "content-length" {
                    resp.headers_mut().insert(k.clone(), v.clone());
                }
            }
            return resp;
        }

        let resp_body = match response.bytes().await {
            Ok(b) => b,
            Err(e) => {
                return error_response(&format!("Failed to read response: {}", e));
            }
        };

        let resp_text = String::from_utf8_lossy(&resp_body);

        if is_rate_limit_or_quota_error(status, &resp_text) {
            warn!("[Desktop OpenAI] Rate limit/quota error detected: {}", status);
            if is_token_limit_error(&resp_text) {
                record_limit_reached(
                    &session_guard,
                    &serde_json::from_slice(&body).unwrap_or(serde_json::json!({})),
                    &format!("Token limit: {}", resp_text),
                    status,
                ).await;
            }
        }

        let mut resp = Response::new(Body::from(resp_body));
        *resp.status_mut() = status;
        for (k, v) in &resp_headers {
            if k != "content-length" {
                resp.headers_mut().insert(k.clone(), v.clone());
            }
        }
        return resp;
    }
}

pub async fn handle_desktop_v1_proxy(
    State(state): State<Arc<Mutex<AppState>>>,
    axum::extract::OriginalUri(uri): axum::extract::OriginalUri,
    headers: HeaderMap,
    body: Bytes,
) -> Response {
    let (warp_resolver, session_guard) = {
        let s = state.lock().await;
        (s.proxy.warp_resolver.clone(), s.proxy.session_guard.clone())
    };

    let client = create_shared_client();
    let path = uri.path();
    let url = format!("{}{}", OPENAI_BASE, path);

    let mut retry_count = 0;
    loop {
        let mut req_builder = client.post(&url).body(body.clone());

        for (key, value) in headers.iter() {
            if key == "host" || key == "connection" {
                continue;
            }
            req_builder = req_builder.header(key, value);
        }

        let response = match req_builder.send().await {
            Ok(r) => r,
            Err(e) => {
                return error_response(&format!("Request failed: {}", e));
            }
        };

        if response.status() == 429 {
            retry_count += 1;
            if retry_count > warp_resolver.max_retries {
                record_limit_reached(
                    &session_guard,
                    &serde_json::from_slice(&body).unwrap_or(serde_json::json!({})),
                    "Desktop v1 proxy: Rate limit exceeded after WARP resets",
                    StatusCode::TOO_MANY_REQUESTS,
                ).await;
                return error_response("Rate limit exceeded after WARP resets");
            }
            info!(
                "[Desktop] 429 received, WARP reset (attempt {}/{})",
                retry_count, warp_resolver.max_retries
            );
            if !warp_resolver.handle_429(retry_count - 1).await {
                record_limit_reached(
                    &session_guard,
                    &serde_json::from_slice(&body).unwrap_or(serde_json::json!({})),
                    "Desktop v1 proxy: WARP reset failed",
                    StatusCode::TOO_MANY_REQUESTS,
                ).await;
                return error_response("WARP reset failed");
            }
            continue;
        }

        let status = response.status();
        let resp_headers = response.headers().clone();

        let resp_body = match response.bytes().await {
            Ok(b) => b,
            Err(e) => {
                return error_response(&format!("Failed to read response: {}", e));
            }
        };

        let mut resp = Response::new(Body::from(resp_body));
        *resp.status_mut() = status;
        for (k, v) in &resp_headers {
            if k != "content-length" {
                resp.headers_mut().insert(k.clone(), v.clone());
            }
        }
        return resp;
    }
}
