use axum::{
    extract::State,
    http::StatusCode,
    response::{Html, IntoResponse},
    Json,
};
use serde_json::json;
use std::sync::Arc;
use tokio::sync::Mutex;
use tracing::info;

use crate::config::{ProxyConfig, OpenCodeFolders};
use crate::proxy::server::AppState;

pub async fn serve_dashboard() -> Html<&'static str> {
    Html(DASHBOARD_HTML)
}

pub async fn handle_api_status(
    State(state): State<Arc<Mutex<AppState>>>,
) -> impl IntoResponse {
    let (listen, upstream, max_retries, warp_delay, log_count) = {
        let state_guard = state.lock().await;
        (
            state_guard.proxy.config.listen_addr.clone(),
            state_guard.proxy.config.opencode_base_url.clone(),
            state_guard.proxy.config.max_retries,
            state_guard.proxy.config.warp_reset_delay_ms,
            state_guard.logs.len(),
        )
    };

    let warp_status = check_warp_status().await;

    Json(json!({
        "proxy": {
            "listen": listen,
            "upstream": upstream,
            "max_retries": max_retries,
            "warp_delay_ms": warp_delay
        },
        "warp": warp_status,
        "logs_count": log_count,
        "uptime": std::time::SystemTime::now()
            .duration_since(std::time::UNIX_EPOCH)
            .map(|d| d.as_secs())
            .unwrap_or(0)
    }))
}

pub async fn handle_api_models(
    State(state): State<Arc<Mutex<AppState>>>,
) -> impl IntoResponse {
    let (base_url, api_key) = {
        let state_guard = state.lock().await;
        (
            state_guard.proxy.config.opencode_base_url.clone(),
            state_guard.proxy.config.opencode_api_key.clone(),
        )
    };

    let models_url = format!("{}/v1/models", base_url.trim_end_matches('/'));

    let mut request = reqwest::Client::new()
        .get(&models_url)
        .header("Accept", "application/json");

    if let Some(key) = &api_key {
        request = request.header("Authorization", format!("Bearer {}", key));
    }

    match request.send().await {
        Ok(resp) if resp.status().is_success() => {
            match resp.json::<serde_json::Value>().await {
                Ok(data) => (StatusCode::OK, Json(data)).into_response(),
                Err(_) => (StatusCode::OK, Json(ProxyConfig::models_response())).into_response(),
            }
        }
        _ => (StatusCode::OK, Json(ProxyConfig::models_response())).into_response(),
    }
}

pub async fn handle_api_logs(
    State(state): State<Arc<Mutex<AppState>>>,
) -> impl IntoResponse {
    let logs = {
        let state_guard = state.lock().await;
        state_guard.logs.iter().rev().take(100).cloned().collect::<Vec<_>>()
    };

    Json(json!({
        "logs": logs,
        "count": logs.len()
    }))
}

pub async fn handle_api_config(
    State(state): State<Arc<Mutex<AppState>>>,
) -> impl IntoResponse {
    let (listen, upstream, api_key, max_retries, warp_delay) = {
        let state_guard = state.lock().await;
        (
            state_guard.proxy.config.listen_addr.clone(),
            state_guard.proxy.config.opencode_base_url.clone(),
            state_guard.proxy.config.opencode_api_key.clone(),
            state_guard.proxy.config.max_retries,
            state_guard.proxy.config.warp_reset_delay_ms,
        )
    };

    Json(json!({
        "listen": listen,
        "upstream": upstream,
        "api_key": api_key,
        "max_retries": max_retries,
        "warp_delay_ms": warp_delay,
        "free_models": ProxyConfig::free_models()
            .iter()
            .map(|m| json!({"id": m.id, "name": m.display_name}))
            .collect::<Vec<_>>()
    }))
}

pub async fn handle_api_reset_ip(
    State(_state): State<Arc<Mutex<AppState>>>,
) -> impl IntoResponse {
    info!("IP reset requested from dashboard");

    match crate::warp::reset_warp_external().await {
        Ok(msg) => (StatusCode::OK, Json(json!({
            "success": true,
            "message": msg
        }))).into_response(),
        Err(e) => (StatusCode::INTERNAL_SERVER_ERROR, Json(json!({
            "success": false,
            "error": e
        }))).into_response(),
    }
}

pub async fn handle_api_desktop_status() -> impl IntoResponse {
    let bypass = crate::bypass::DesktopBypass::new();
    let status = bypass.status();

    Json(json!({
        "config_found": status.config_found,
        "config_path": status.config_path,
        "is_proxied": status.is_proxied,
        "api_base_url": status.api_base_url,
        "api_key": status.api_key,
        "backup_exists": status.backup_exists
    }))
}

pub async fn handle_api_setup_desktop(
    State(state): State<Arc<Mutex<AppState>>>,
) -> impl IntoResponse {
    let listen_addr = {
        let state_guard = state.lock().await;
        state_guard.proxy.config.listen_addr.clone()
    };

    let bypass = crate::bypass::DesktopBypass::new();

    match bypass.enable(&listen_addr) {
        Ok(msg) => (StatusCode::OK, Json(json!({
            "success": true,
            "message": msg
        }))).into_response(),
        Err(e) => (StatusCode::INTERNAL_SERVER_ERROR, Json(json!({
            "success": false,
            "error": e
        }))).into_response(),
    }
}

pub async fn handle_api_restore_desktop() -> impl IntoResponse {
    let bypass = crate::bypass::DesktopBypass::new();

    match bypass.disable() {
        Ok(msg) => (StatusCode::OK, Json(json!({
            "success": true,
            "message": msg
        }))).into_response(),
        Err(e) => (StatusCode::INTERNAL_SERVER_ERROR, Json(json!({
            "success": false,
            "error": e
        }))).into_response(),
    }
}

pub async fn handle_api_sessions(
    State(state): State<Arc<Mutex<AppState>>>,
) -> impl IntoResponse {
    let session_guard = {
        let state_guard = state.lock().await;
        state_guard.proxy.session_guard.clone()
    };

    match session_guard.get_health_report().await {
        report => (StatusCode::OK, Json(report)).into_response(),
    }
}

pub async fn handle_api_restore_ip(
    State(_state): State<Arc<Mutex<AppState>>>,
) -> impl IntoResponse {
    info!("IP restoration requested from dashboard");

    match crate::warp::restore_ip_external().await {
        Ok(msg) => {
            let parsed: serde_json::Value = serde_json::from_str(&msg)
                .unwrap_or_else(|_| serde_json::json!({"message": msg}));
            (StatusCode::OK, Json(json!({
                "success": true,
                "result": parsed
            }))).into_response()
        }
        Err(e) => (StatusCode::INTERNAL_SERVER_ERROR, Json(json!({
            "success": false,
            "error": e
        }))).into_response(),
    }
}

pub async fn handle_api_network_backup() -> impl IntoResponse {
    let manager = crate::network::NetworkManager::new();
    manager.init().await;

    match manager.capture_snapshot("manual_backup").await {
        Ok(snapshot) => (StatusCode::OK, Json(json!({
            "success": true,
            "snapshot": snapshot
        }))).into_response(),
        Err(e) => (StatusCode::INTERNAL_SERVER_ERROR, Json(json!({
            "success": false,
            "error": e
        }))).into_response(),
    }
}

pub async fn handle_api_network_status() -> impl IntoResponse {
    let manager = crate::network::NetworkManager::new();
    manager.init().await;

    let current = manager.get_current_state().await;
    let backup_exists = manager.backup_exists().await;
    let backup = manager.load_backup().await;

    match current {
        Ok(state) => (StatusCode::OK, Json(json!({
            "success": true,
            "current": state,
            "backup_exists": backup_exists,
            "backup": backup
        }))).into_response(),
        Err(e) => (StatusCode::INTERNAL_SERVER_ERROR, Json(json!({
            "success": false,
            "error": e
        }))).into_response(),
    }
}

pub async fn handle_api_network_restore() -> impl IntoResponse {
    let manager = crate::network::NetworkManager::new();
    manager.init().await;

    match manager.restore_network().await {
        Ok(result) => (StatusCode::OK, Json(json!({
            "success": result.success,
            "result": result
        }))).into_response(),
        Err(e) => (StatusCode::INTERNAL_SERVER_ERROR, Json(json!({
            "success": false,
            "error": e
        }))).into_response(),
    }
}

pub async fn handle_api_opencode_folders() -> impl IntoResponse {
    let folders = OpenCodeFolders::detect();
    let summary = folders.get_summary();
    (StatusCode::OK, Json(summary)).into_response()
}

pub async fn handle_api_clear_cache() -> impl IntoResponse {
    info!("Cache clear requested from dashboard");
    let folders = OpenCodeFolders::detect();
    match folders.clear_cache() {
        Ok(result) => (StatusCode::OK, Json(result)).into_response(),
        Err(e) => (StatusCode::INTERNAL_SERVER_ERROR, Json(json!({
            "success": false,
            "error": e
        }))).into_response(),
    }
}

pub async fn handle_api_clear_all_data() -> impl IntoResponse {
    info!("Full data clear requested from dashboard");
    let folders = OpenCodeFolders::detect();
    match folders.clear_all_data() {
        Ok(result) => (StatusCode::OK, Json(result)).into_response(),
        Err(e) => (StatusCode::INTERNAL_SERVER_ERROR, Json(json!({
            "success": false,
            "error": e
        }))).into_response(),
    }
}

async fn check_warp_status() -> serde_json::Value {
    if cfg!(target_os = "windows") || cfg!(target_os = "linux") || cfg!(target_os = "macos") {
        match tokio::process::Command::new("warp-cli")
            .arg("status")
            .output()
            .await
        {
            Ok(output) => {
                let status_str = String::from_utf8_lossy(&output.stdout).to_string();
                let connected = status_str.contains("Connected") || status_str.contains("connected");
                json!({
                    "installed": true,
                    "connected": connected,
                    "raw": status_str.trim()
                })
            }
            Err(_) => json!({
                "installed": false,
                "connected": false,
                "raw": "warp-cli not found"
            })
        }
    } else {
        json!({
            "installed": false,
            "connected": false,
            "raw": "unsupported platform"
        })
    }
}

static DASHBOARD_HTML: &str = r#"<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Oplire - Panel de Control</title>
<link rel="icon" href="data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 32 32'><rect width='32' height='32' rx='8' fill='url(%23g)'/><defs><linearGradient id='g' x1='0' y1='0' x2='32' y2='32'><stop offset='0%' stop-color='%236366f1'/><stop offset='50%' stop-color='%238b5cf6'/><stop offset='100%' stop-color='%23a855f7'/></linearGradient></defs><text x='16' y='23' text-anchor='middle' font-size='18' font-weight='900' fill='white'>O</text></svg>">
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800;900&family=JetBrains+Mono:wght@400;500;600&display=swap" rel="stylesheet">
<style>
*{margin:0;padding:0;box-sizing:border-box}
:root{
  --bg:#06060a;--bg2:#0c0c12;--surface:#12121a;--surface2:#18181f;--surface3:#1e1e28;
  --border:rgba(255,255,255,.05);--border2:rgba(255,255,255,.08);--border3:rgba(255,255,255,.12);
  --accent:#6366f1;--accent2:#818cf8;--accent3:#a78bfa;--accent-glow:rgba(99,102,241,.12);
  --emerald:#34d399;--emerald2:#10b981;--emerald-glow:rgba(52,211,153,.1);
  --rose:#fb7185;--rose2:#f43f5e;--rose-glow:rgba(251,113,133,.1);
  --amber:#fbbf24;--amber2:#f59e0b;--amber-glow:rgba(251,191,36,.1);
  --cyan:#22d3ee;--cyan2:#06b6d4;--cyan-glow:rgba(34,211,238,.1);
  --text:#f4f4f5;--text2:#a1a1aa;--text3:#71717a;--dim:#52525b;--dim2:#3f3f46;
  --font:'Inter',system-ui,-apple-system,sans-serif;
  --mono:'JetBrains Mono',monospace;
  --radius:14px;--radius-lg:18px;--radius-xl:22px;
  --shadow-sm:0 1px 3px rgba(0,0,0,.3);
  --shadow-md:0 4px 16px rgba(0,0,0,.35);
  --shadow-lg:0 12px 40px rgba(0,0,0,.4);
  --shadow-glow:0 0 30px rgba(99,102,241,.08);
}
html{scroll-behavior:smooth}
body{font-family:var(--font);background:var(--bg);color:var(--text);min-height:100vh;line-height:1.6;-webkit-font-smoothing:antialiased;overflow-x:hidden}
::selection{background:var(--accent);color:#fff}

body::before{
  content:'';position:fixed;top:-300px;left:50%;transform:translateX(-50%);
  width:1100px;height:1100px;
  background:radial-gradient(circle,rgba(99,102,241,.04) 0%,rgba(129,140,248,.02) 30%,transparent 60%);
  pointer-events:none;z-index:0
}
body::after{
  content:'';position:fixed;bottom:-200px;right:-100px;
  width:600px;height:600px;
  background:radial-gradient(circle,rgba(52,211,153,.03) 0%,transparent 60%);
  pointer-events:none;z-index:0
}

@keyframes fadeIn{from{opacity:0;transform:translateY(20px)}to{opacity:1;transform:translateY(0)}}
@keyframes fadeInUp{from{opacity:0;transform:translateY(30px)}to{opacity:1;transform:translateY(0)}}
@keyframes fadeInScale{from{opacity:0;transform:scale(.95) translateY(10px)}to{opacity:1;transform:scale(1) translateY(0)}}
@keyframes slideDown{from{opacity:0;transform:translateY(-10px)}to{opacity:1;transform:translateY(0)}}
@keyframes scaleIn{from{opacity:0;transform:scale(.9)}to{opacity:1;transform:scale(1)}}
@keyframes pulse{0%,100%{opacity:1}50%{opacity:.6}}
@keyframes shimmer{0%{background-position:-200% 0}100%{background-position:200% 0}}
@keyframes float{0%,100%{transform:translateY(0)}50%{transform:translateY(-6px)}}
@keyframes breathe{0%,100%{box-shadow:0 0 0 0 var(--emerald-glow)}50%{box-shadow:0 0 0 10px transparent}}
@keyframes glow{0%,100%{box-shadow:0 0 20px rgba(99,102,241,.15)}50%{box-shadow:0 0 40px rgba(99,102,241,.25)}}
@keyframes borderGlow{0%,100%{border-color:rgba(99,102,241,.15)}50%{border-color:rgba(99,102,241,.3)}}
@keyframes spin{from{transform:rotate(0deg)}to{transform:rotate(360deg)}}
@keyframes ripple{to{transform:scale(4);opacity:0}}

.header{
  background:rgba(6,6,10,.9);
  border-bottom:1px solid var(--border);
  padding:0 44px;height:72px;
  display:flex;align-items:center;justify-content:space-between;
  position:sticky;top:0;z-index:100;
  backdrop-filter:blur(32px) saturate(200%);
  -webkit-backdrop-filter:blur(32px) saturate(200%)
}
.header-left{display:flex;align-items:center;gap:18px}
.logo{
  width:44px;height:44px;
  background:linear-gradient(135deg,#6366f1,#818cf8,#a78bfa);
  border-radius:14px;display:flex;align-items:center;justify-content:center;
  font-size:20px;font-weight:900;color:#fff;
  box-shadow:0 4px 20px rgba(99,102,241,.35),0 0 0 1px rgba(255,255,255,.12) inset;
  animation:float 4s ease-in-out infinite;
  position:relative
}
.logo::after{
  content:'';position:absolute;inset:-2px;border-radius:16px;
  background:linear-gradient(135deg,#6366f1,#a78bfa);
  z-index:-1;opacity:0;transition:opacity .3s
}
.header:hover .logo::after{opacity:.3}
.header h1{font-size:22px;font-weight:900;letter-spacing:-.5px;color:var(--text);background:linear-gradient(135deg,#f4f4f5,#a1a1aa);-webkit-background-clip:text;-webkit-text-fill-color:transparent}
.header .tagline{color:var(--text3);font-size:11px;margin-top:2px;font-weight:500;letter-spacing:.3px}
.header-right{display:flex;align-items:center;gap:14px}
.github-btn{
  display:flex;align-items:center;gap:8px;padding:9px 18px;
  background:var(--surface);border:1px solid var(--border2);border-radius:var(--radius);
  color:var(--text2);text-decoration:none;font-size:12px;font-weight:600;
  transition:all .3s cubic-bezier(.4,0,.2,1)
}
.github-btn:hover{
  border-color:var(--accent);color:var(--text);background:var(--surface2);
  box-shadow:var(--shadow-glow);transform:translateY(-2px)
}
.github-btn svg{width:16px;height:16px;fill:currentColor}
.nav{display:flex;gap:3px;background:var(--surface);border:1px solid var(--border);border-radius:var(--radius);padding:4px}
.nav button{
  background:transparent;border:none;color:var(--text3);
  padding:10px 18px;border-radius:10px;cursor:pointer;
  font-size:12px;font-weight:600;transition:all .3s cubic-bezier(.4,0,.2,1);
  font-family:inherit;position:relative;overflow:hidden
}
.nav button:hover{color:var(--text2);background:rgba(255,255,255,.04)}
.nav button.active{
  background:linear-gradient(135deg,#6366f1,#818cf8);
  color:#fff;font-weight:700;
  box-shadow:0 2px 16px rgba(99,102,241,.4),0 0 0 1px rgba(255,255,255,.15) inset
}

.main{max-width:1400px;margin:0 auto;padding:36px 44px;position:relative;z-index:1}

.stats{display:grid;grid-template-columns:repeat(4,1fr);gap:18px;margin-bottom:32px}
.stat{
  background:linear-gradient(160deg,var(--surface),var(--surface2));
  border:1px solid var(--border);border-radius:var(--radius-lg);padding:26px;
  transition:all .4s cubic-bezier(.4,0,.2,1);position:relative;overflow:hidden;
  animation:fadeInScale .6s ease backwards
}
.stat:nth-child(1){animation-delay:.05s}
.stat:nth-child(2){animation-delay:.1s}
.stat:nth-child(3){animation-delay:.15s}
.stat:nth-child(4){animation-delay:.2s}
.stat::before{
  content:'';position:absolute;top:0;left:0;right:0;height:1px;
  background:linear-gradient(90deg,transparent,rgba(255,255,255,.06),transparent);
  opacity:0;transition:opacity .3s
}
.stat::after{
  content:'';position:absolute;inset:0;border-radius:var(--radius-lg);
  background:radial-gradient(circle at 50% 0%,rgba(255,255,255,.02),transparent 60%);
  pointer-events:none;opacity:0;transition:opacity .3s
}
.stat:hover{
  border-color:var(--border2);transform:translateY(-4px);
  box-shadow:var(--shadow-lg),var(--shadow-glow)
}
.stat:hover::before{opacity:1}
.stat:hover::after{opacity:1}
.stat-icon{
  width:48px;height:48px;border-radius:14px;
  display:flex;align-items:center;justify-content:center;margin-bottom:20px;
  transition:all .4s cubic-bezier(.4,0,.2,1)
}
.stat:hover .stat-icon{transform:scale(1.1) rotate(-3deg)}
.stat-icon svg{width:24px;height:24px}
.stat-icon.indigo{background:var(--accent-glow);border:1px solid rgba(99,102,241,.12)}
.stat-icon.indigo svg{fill:var(--accent)}
.stat-icon.emerald{background:var(--emerald-glow);border:1px solid rgba(52,211,153,.12)}
.stat-icon.emerald svg{fill:var(--emerald)}
.stat-icon.purple{background:rgba(167,139,250,.1);border:1px solid rgba(167,139,250,.12)}
.stat-icon.purple svg{fill:var(--accent3)}
.stat-icon.amber{background:var(--amber-glow);border:1px solid rgba(251,191,36,.12)}
.stat-icon.amber svg{fill:var(--amber)}
.stat-icon.cyan{background:var(--cyan-glow);border:1px solid rgba(34,211,238,.12)}
.stat-icon.cyan svg{fill:var(--cyan)}
.stat-icon.rose{background:var(--rose-glow);border:1px solid rgba(251,113,133,.12)}
.stat-icon.rose svg{fill:var(--rose)}
.stat-label{font-size:11px;text-transform:uppercase;letter-spacing:1.8px;color:var(--text3);margin-bottom:10px;font-weight:700}
.stat-value{font-size:30px;font-weight:900;line-height:1;letter-spacing:-.7px}
.stat-value.emerald{color:var(--emerald)}
.stat-value.rose{color:var(--rose)}
.stat-value.indigo{color:var(--accent)}
.stat-value.purple{color:var(--accent3)}
.stat-value.amber{color:var(--amber)}
.stat-value.cyan{color:var(--cyan)}
.stat-sub{font-size:11px;color:var(--text3);margin-top:14px;display:flex;align-items:center;gap:6px}
.stat-sub code{
  background:rgba(0,0,0,.4);padding:4px 10px;border-radius:6px;
  font-family:var(--mono);font-size:10px;border:1px solid var(--border);
  letter-spacing:.3px;color:var(--text2)
}

.dot{display:inline-block;width:10px;height:10px;border-radius:50%;margin-right:8px;vertical-align:middle}
.dot.on{background:var(--emerald);box-shadow:0 0 12px var(--emerald);animation:breathe 2.5s ease-in-out infinite}
.dot.off{background:var(--rose);box-shadow:0 0 12px var(--rose)}

.panel{
  background:linear-gradient(160deg,var(--surface),var(--surface2));
  border:1px solid var(--border);border-radius:var(--radius-xl);padding:34px;margin-bottom:26px;
  position:relative;overflow:hidden;
  animation:fadeIn .6s ease backwards
}
.panel::before{
  content:'';position:absolute;top:0;left:0;bottom:0;width:3px;
  background:linear-gradient(180deg,#6366f1,#818cf8,#a78bfa);
  border-radius:0 3px 3px 0
}
.panel-head{display:flex;align-items:center;justify-content:space-between;margin-bottom:26px}
.panel-title{font-size:17px;font-weight:800;color:var(--text);display:flex;align-items:center;gap:12px;letter-spacing:-.2px}
.badge{
  background:linear-gradient(135deg,#6366f1,#818cf8);color:#fff;
  padding:5px 14px;border-radius:24px;font-size:10px;font-weight:700;
  letter-spacing:.8px;text-transform:uppercase;
  box-shadow:0 2px 10px rgba(99,102,241,.3)
}
.badge.emerald{background:linear-gradient(135deg,#10b981,#34d399);box-shadow:0 2px 10px rgba(52,211,153,.3)}
.badge.rose{background:linear-gradient(135deg,#f43f5e,#fb7185);box-shadow:0 2px 10px rgba(251,113,133,.3)}
.badge.amber{background:linear-gradient(135deg,#f59e0b,#fbbf24);box-shadow:0 2px 10px rgba(251,191,36,.3)}
.badge.cyan{background:linear-gradient(135deg,#06b6d4,#22d3ee);box-shadow:0 2px 10px rgba(34,211,238,.3)}

.actions{display:flex;gap:12px;flex-wrap:wrap}
.btn{
  padding:12px 24px;border-radius:var(--radius);border:none;cursor:pointer;
  font-size:13px;font-weight:700;transition:all .3s cubic-bezier(.4,0,.2,1);
  display:inline-flex;align-items:center;gap:9px;font-family:inherit;
  letter-spacing:.1px;position:relative;overflow:hidden
}
.btn::after{
  content:'';position:absolute;inset:0;
  background:linear-gradient(135deg,rgba(255,255,255,.1),transparent);
  opacity:0;transition:opacity .2s;border-radius:inherit
}
.btn:hover::after{opacity:1}
.btn:active{transform:scale(.97)}
.btn svg{width:18px;height:18px;flex-shrink:0;position:relative;z-index:1}
.btn span{position:relative;z-index:1}
.btn-primary{
  background:linear-gradient(135deg,#6366f1,#818cf8);color:#fff;
  box-shadow:0 4px 20px rgba(99,102,241,.35),0 0 0 1px rgba(255,255,255,.1) inset
}
.btn-primary:hover{transform:translateY(-2px);box-shadow:0 8px 32px rgba(99,102,241,.45)}
.btn-danger{
  background:linear-gradient(135deg,#f43f5e,#fb7185);color:#fff;
  box-shadow:0 4px 20px rgba(244,63,94,.3),0 0 0 1px rgba(255,255,255,.1) inset
}
.btn-danger:hover{transform:translateY(-2px);box-shadow:0 8px 32px rgba(244,63,94,.4)}
.btn-ghost{
  background:transparent;color:var(--text2);
  border:1px solid var(--border2)
}
.btn-ghost:hover{
  border-color:var(--accent);color:var(--accent);
  background:var(--accent-glow);transform:translateY(-2px)
}
.btn-emerald{
  background:transparent;color:var(--emerald);
  border:1px solid rgba(52,211,153,.2)
}
.btn-emerald:hover{
  background:var(--emerald-glow);border-color:var(--emerald);
  transform:translateY(-2px);box-shadow:0 4px 20px rgba(52,211,153,.2)
}
.btn-amber{
  background:transparent;color:var(--amber);
  border:1px solid rgba(251,191,36,.2)
}
.btn-amber:hover{
  background:var(--amber-glow);border-color:var(--amber);
  transform:translateY(-2px);box-shadow:0 4px 20px rgba(251,191,36,.2)
}
.btn-cyan{
  background:transparent;color:var(--cyan);
  border:1px solid rgba(34,211,238,.2)
}
.btn-cyan:hover{
  background:var(--cyan-glow);border-color:var(--cyan);
  transform:translateY(-2px);box-shadow:0 4px 20px rgba(34,211,238,.2)
}

.log-area{
  background:var(--bg);border:1px solid var(--border);border-radius:var(--radius);
  padding:22px;max-height:480px;overflow-y:auto;
  font-family:var(--mono);font-size:11px;line-height:2.1
}
.log-row{
  padding:6px 10px;border-bottom:1px solid rgba(255,255,255,.02);
  display:flex;gap:14px;transition:all .15s;border-radius:8px
}
.log-row:last-child{border:none}
.log-row:hover{background:rgba(255,255,255,.02)}
.log-time{color:var(--accent);font-weight:600;min-width:85px;opacity:.9}
.log-msg{color:var(--text2)}

.model-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(320px,1fr));gap:14px}
.model-item{
  background:var(--bg);border:1px solid var(--border);border-radius:var(--radius);
  padding:22px;transition:all .35s cubic-bezier(.4,0,.2,1);position:relative;overflow:hidden
}
.model-item::before{
  content:'';position:absolute;top:0;left:0;right:0;height:2px;
  background:linear-gradient(90deg,var(--accent),var(--accent2));
  opacity:0;transition:opacity .3s
}
.model-item:hover{border-color:rgba(99,102,241,.2);background:var(--surface);transform:translateY(-3px);box-shadow:var(--shadow-md)}
.model-item:hover::before{opacity:1}
.model-id{
  color:var(--accent);font-family:var(--mono);font-size:11px;font-weight:600;
  background:var(--accent-glow);padding:4px 10px;border-radius:8px;
  display:inline-block;margin-bottom:10px;border:1px solid rgba(99,102,241,.1)
}
.model-name{color:var(--text);font-size:15px;font-weight:700;margin-bottom:6px}
.model-meta{color:var(--text3);font-size:11px;display:flex;gap:14px}
.model-meta span{display:flex;align-items:center;gap:4px}

.config-item{
  display:flex;align-items:center;justify-content:space-between;
  padding:16px 0;border-bottom:1px solid var(--border);transition:all .15s
}
.config-item:last-child{border:none}
.config-item:hover{background:rgba(255,255,255,.01);margin:0 -16px;padding-left:16px;padding-right:16px;border-radius:8px}
.config-key{color:var(--text3);font-size:12px;font-weight:600;text-transform:uppercase;letter-spacing:.5px}
.config-val{
  color:var(--text);font-family:var(--mono);font-size:12px;
  background:var(--bg);padding:8px 14px;border-radius:8px;
  border:1px solid var(--border);transition:all .2s
}
.config-val:hover{border-color:var(--border2)}

.desktop-grid{display:grid;grid-template-columns:1fr 1fr;gap:18px;margin-bottom:28px}
.desktop-tile{
  background:var(--bg);border:1px solid var(--border);border-radius:var(--radius);padding:26px;
  transition:all .3s cubic-bezier(.4,0,.2,1)
}
.desktop-tile:hover{border-color:var(--border2);transform:translateY(-2px);box-shadow:var(--shadow-sm)}
.desktop-tile h4{font-size:10px;text-transform:uppercase;letter-spacing:2px;color:var(--text3);margin-bottom:14px;font-weight:700}
.desktop-tile .val{display:flex;align-items:center;gap:10px;font-size:24px;font-weight:800}
.desktop-tile .path{color:var(--text3);font-family:var(--mono);font-size:11px;margin-top:12px;word-break:break-all;padding:8px 12px;background:rgba(0,0,0,.3);border-radius:8px;border:1px solid var(--border)}

.cache-grid{display:grid;grid-template-columns:1fr 1fr 1fr;gap:18px;margin-bottom:28px}
.cache-tile{
  background:var(--bg);border:1px solid var(--border);border-radius:var(--radius);padding:26px;
  transition:all .3s cubic-bezier(.4,0,.2,1);position:relative;overflow:hidden
}
.cache-tile::before{
  content:'';position:absolute;top:0;left:0;right:0;height:3px;
  opacity:0;transition:opacity .3s
}
.cache-tile:hover{border-color:var(--border2);transform:translateY(-2px);box-shadow:var(--shadow-md)}
.cache-tile:hover::before{opacity:1}
.cache-tile.config::before{background:linear-gradient(90deg,var(--accent),var(--accent2))}
.cache-tile.cache::before{background:linear-gradient(90deg,var(--amber),var(--amber2))}
.cache-tile.data::before{background:linear-gradient(90deg,var(--emerald),var(--emerald2))}
.cache-tile h4{font-size:10px;text-transform:uppercase;letter-spacing:2px;color:var(--text3);margin-bottom:14px;font-weight:700}
.cache-tile .val{font-size:22px;font-weight:800;margin-bottom:8px}
.cache-tile .path{color:var(--text3);font-family:var(--mono);font-size:11px;word-break:break-all;padding:8px 12px;background:rgba(0,0,0,.3);border-radius:8px;border:1px solid var(--border);margin-top:12px}
.cache-tile .size{font-size:13px;color:var(--text2);margin-top:10px;display:flex;align-items:center;gap:6px}
.cache-tile .size .dot{width:8px;height:8px;border-radius:50%;margin-right:0}

.tool-card{
  background:linear-gradient(160deg,var(--surface),var(--surface2));
  border:1px solid var(--border);border-radius:var(--radius-xl);padding:34px;
  transition:all .4s cubic-bezier(.4,0,.2,1);position:relative;overflow:hidden
}
.tool-card::before{
  content:'';position:absolute;top:0;left:0;right:0;height:3px;
  opacity:0;transition:opacity .3s
}
.tool-card:hover{border-color:var(--border2);transform:translateY(-5px);box-shadow:var(--shadow-lg)}
.tool-card:hover::before{opacity:1}
.tool-card.indigo::before{background:linear-gradient(90deg,#6366f1,#a78bfa)}
.tool-card.amber::before{background:linear-gradient(90deg,#f59e0b,#f97316)}
.tool-head{display:flex;align-items:center;gap:18px;margin-bottom:18px}
.tool-icon{
  width:56px;height:56px;border-radius:16px;
  display:flex;align-items:center;justify-content:center;flex-shrink:0;
  transition:all .4s cubic-bezier(.4,0,.2,1)
}
.tool-card:hover .tool-icon{transform:scale(1.1) rotate(-3deg)}
.tool-icon svg{width:28px;height:28px;fill:#fff}
.tool-card.indigo .tool-icon{background:linear-gradient(135deg,#6366f1,#818cf8);box-shadow:0 4px 20px rgba(99,102,241,.35)}
.tool-card.amber .tool-icon{background:linear-gradient(135deg,#f59e0b,#f97316);box-shadow:0 4px 20px rgba(245,158,11,.35)}
.tool-head h3{font-size:20px;font-weight:800;color:var(--text);letter-spacing:-.3px}
.tool-head .tag{
  font-size:10px;padding:5px 12px;border-radius:16px;font-weight:700;
  letter-spacing:.6px;margin-left:auto
}
.tool-card.indigo .tag{background:var(--accent-glow);color:var(--accent);border:1px solid rgba(99,102,241,.12)}
.tool-card.amber .tag{background:var(--amber-glow);color:var(--amber);border:1px solid rgba(245,158,11,.12)}
.tool-card p{color:var(--text3);font-size:14px;line-height:1.8;margin-bottom:26px}
.tool-link{
  display:inline-flex;align-items:center;gap:8px;padding:12px 24px;border-radius:var(--radius);
  font-size:13px;font-weight:700;text-decoration:none;transition:all .3s cubic-bezier(.4,0,.2,1);
  position:relative;overflow:hidden
}
.tool-link::after{
  content:'';position:absolute;inset:0;
  background:linear-gradient(135deg,rgba(255,255,255,.15),transparent);
  opacity:0;transition:opacity .2s
}
.tool-link:hover::after{opacity:1}
.tool-link svg{width:16px;height:16px;fill:currentColor;position:relative;z-index:1}
.tool-link span{position:relative;z-index:1}
.tool-card.indigo .tool-link{background:linear-gradient(135deg,#6366f1,#818cf8);color:#fff;box-shadow:0 4px 20px rgba(99,102,241,.35)}
.tool-card.indigo .tool-link:hover{box-shadow:0 8px 32px rgba(99,102,241,.5);transform:translateY(-2px)}
.tool-card.amber .tool-link{background:linear-gradient(135deg,#f59e0b,#f97316);color:#000;box-shadow:0 4px 20px rgba(245,158,11,.35)}
.tool-card.amber .tool-link:hover{box-shadow:0 8px 32px rgba(245,158,11,.5);transform:translateY(-2px)}
.tools-grid{display:grid;grid-template-columns:1fr 1fr;gap:18px}

.toast{
  position:fixed;bottom:32px;right:32px;
  background:var(--emerald);color:#fff;
  padding:16px 32px;border-radius:var(--radius);font-weight:700;font-size:13px;font-family:inherit;
  opacity:0;transition:all .5s cubic-bezier(.4,0,.2,1);
  pointer-events:none;z-index:1000;
  box-shadow:var(--shadow-lg),0 0 0 1px rgba(255,255,255,.15) inset;
  transform:translateY(20px) scale(.9)
}
.toast.show{opacity:1;transform:translateY(0) scale(1)}
.toast.error{background:var(--rose);color:#fff}

.footer{text-align:center;padding:40px;color:var(--text3);font-size:11px;border-top:1px solid var(--border);margin-top:56px}
.footer strong{color:var(--text2);font-weight:700}
.footer a{color:var(--accent);text-decoration:none;transition:all .2s;font-weight:600}
.footer a:hover{color:var(--accent2);text-decoration:underline}

::-webkit-scrollbar{width:6px}
::-webkit-scrollbar-track{background:transparent}
::-webkit-scrollbar-thumb{background:var(--dim2);border-radius:4px}
::-webkit-scrollbar-thumb:hover{background:var(--dim)}

@media(max-width:1200px){.stats{grid-template-columns:repeat(2,1fr)}.cache-grid{grid-template-columns:1fr 1fr}}
@media(max-width:1024px){.tools-grid{grid-template-columns:1fr}}
@media(max-width:768px){
  .main{padding:20px}
  .stats{grid-template-columns:1fr}
  .cache-grid{grid-template-columns:1fr}
  .header{padding:0 20px;height:auto;flex-direction:column;gap:12px;padding:14px 20px}
  .header-right{flex-wrap:wrap;justify-content:center}
  .nav{flex-wrap:wrap;justify-content:center}
  .desktop-grid{grid-template-columns:1fr}
}
</style>
</head>
<body>

<div class="header">
  <div class="header-left">
    <div class="logo">O</div>
    <div>
      <h1>Oplire</h1>
      <div class="tagline">Sistema de Rotacion de IP y Proxy Profesional</div>
    </div>
  </div>
  <div class="header-right">
    <div class="nav">
      <button class="active" onclick="showSection('overview')">Principal</button>
      <button onclick="showSection('models')">Modelos</button>
      <button onclick="showSection('logs')">Registros</button>
      <button onclick="showSection('config')">Config</button>
      <button onclick="showSection('desktop')">Desktop</button>
      <button onclick="showSection('cache')">Cache</button>
      <button onclick="showSection('programs')">Herramientas</button>
    </div>
    <a href="https://github.com/PolloCraft/Oplire-OpenCode" target="_blank" class="github-btn">
      <svg viewBox="0 0 24 24"><path d="M12 0c-6.626 0-12 5.373-12 12 0 5.302 3.438 9.8 8.207 11.387.599.111.793-.261.793-.577v-2.234c-3.338.726-4.033-1.416-4.033-1.416-.546-1.387-1.333-1.756-1.333-1.756-1.089-.745.083-.729.083-.729 1.205.084 1.839 1.237 1.839 1.237 1.07 1.834 2.807 1.304 3.492.997.107-.775.418-1.305.762-1.604-2.665-.305-5.467-1.334-5.467-5.931 0-1.311.469-2.381 1.236-3.221-.124-.303-.535-1.524.117-3.176 0 0 1.008-.322 3.301 1.23.957-.266 1.983-.399 3.003-.404 1.02.005 2.047.138 3.006.404 2.291-1.552 3.297-1.23 3.297-1.23.653 1.653.242 2.874.118 3.176.77.84 1.235 1.911 1.235 3.221 0 4.609-2.807 5.624-5.479 5.921.43.372.823 1.102.823 2.222v3.293c0 .319.192.694.801.576 4.765-1.589 8.199-6.086 8.199-11.386 0-6.627-5.373-12-12-12z"/></svg>
      GitHub
    </a>
  </div>
</div>

<div class="main">

  <div id="overview">
    <div class="stats">
      <div class="stat">
        <div class="stat-icon indigo"><svg viewBox="0 0 24 24"><path d="M7 2v11h3v9l7-12h-4l4-8z"/></svg></div>
        <div class="stat-label">Estado del Proxy</div>
        <div class="stat-value emerald" id="proxy-status"><span class="dot on"></span>Activo</div>
        <div class="stat-sub" id="proxy-listen"><code>127.0.0.1:8080</code></div>
      </div>
      <div class="stat">
        <div class="stat-icon emerald"><svg viewBox="0 0 24 24"><path d="M12 1L3 5v6c0 5.55 3.84 10.74 9 12 5.16-1.26 9-6.45 9-12V5l-9-4zm-2 16l-4-4 1.41-1.41L10 14.17l6.59-6.59L18 9l-8 8z"/></svg></div>
        <div class="stat-label">Tunel WARP</div>
        <div class="stat-value" id="warp-status">Verificando...</div>
        <div class="stat-sub" id="warp-detail">Consultando...</div>
      </div>
      <div class="stat">
        <div class="stat-icon purple"><svg viewBox="0 0 24 24"><path d="M3.9 12c0-1.71 1.39-3.1 3.1-3.1h4V7H7c-2.76 0-5 2.24-5 5s2.24 5 5 5h4v-1.9H7c-1.71 0-3.1-1.39-3.1-3.1zM8 13h8v-2H8v2zm9-6h-4v1.9h4c1.71 0 3.1 1.39 3.1 3.1s-1.39 3.1-3.1 3.1h-4V17h4c2.76 0 5-2.24 5-5s-2.24-5-5-5z"/></svg></div>
        <div class="stat-label">Servidor Upstream</div>
        <div class="stat-value purple" id="upstream-url" style="font-size:17px">-</div>
        <div class="stat-sub">OpenCode Zen</div>
      </div>
      <div class="stat">
        <div class="stat-icon amber"><svg viewBox="0 0 24 24"><path d="M12 4V1L8 5l4 4V6c3.31 0 6 2.69 6 6 0 1.01-.25 1.97-.7 2.8l1.46 1.46C19.54 15.03 20 13.57 20 12c0-4.42-3.58-8-8-8zm0 14c-3.31 0-6-2.69-6-6 0-1.01.25-1.97.7-2.8L5.24 7.74C4.46 8.97 4 10.43 4 12c0 4.42 3.58 8 8 8v3l4-4-4-4v3z"/></svg></div>
        <div class="stat-label">Reintentos</div>
        <div class="stat-value amber" id="max-retries">3</div>
        <div class="stat-sub">Intentos de reset WARP</div>
      </div>
    </div>

    <div class="panel">
      <div class="panel-head">
        <div class="panel-title">Acciones Rapidas <span class="badge">ACCIONES</span></div>
      </div>
      <div class="actions">
        <button class="btn btn-primary" onclick="resetIP()">
          <svg viewBox="0 0 24 24" fill="currentColor"><path d="M17.65 6.35C16.2 4.9 14.21 4 12 4c-4.42 0-7.99 3.58-7.99 8s3.57 8 7.99 8c3.73 0 6.84-2.55 7.73-6h-2.08c-.82 2.33-3.04 4-5.65 4-3.31 0-6-2.69-6-6s2.69-6 6-6c1.66 0 3.14.69 4.22 1.78L13 11h7V4l-2.35 2.35z"/></svg>
          <span>Resetear IP (WARP)</span>
        </button>
        <button class="btn btn-ghost" onclick="refreshStatus()">
          <svg viewBox="0 0 24 24" fill="currentColor"><path d="M17.65 6.35C16.2 4.9 14.21 4 12 4c-4.42 0-7.99 3.58-7.99 8s3.57 8 7.99 8c3.73 0 6.84-2.55 7.73-6h-2.08c-.82 2.33-3.04 4-5.65 4-3.31 0-6-2.69-6-6s2.69-6 6-6c1.66 0 3.14.69 4.22 1.78L13 11h7V4l-2.35 2.35z"/></svg>
          <span>Actualizar</span>
        </button>
        <button class="btn btn-danger" onclick="if(confirm('Forzar reinicio del tunel WARP?'))resetIP()">
          <svg viewBox="0 0 24 24" fill="currentColor"><path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm1 15h-2v-2h2v2zm0-4h-2V7h2v6z"/></svg>
          <span>Forzar Reset</span>
        </button>
        <button class="btn btn-emerald" onclick="restoreIP()">
          <svg viewBox="0 0 24 24" fill="currentColor"><path d="M12 5V1L7 6l5 5V7c3.31 0 6 2.69 6 6s-2.69 6-6 6-6-2.69-6-6H4c0 4.42 3.58 8 8 8s8-3.58 8-8-3.58-8-8-8z"/></svg>
          <span>Restaurar IP</span>
        </button>
      </div>
    </div>
  </div>

  <div id="models" style="display:none">
    <div class="panel">
      <div class="panel-head">
        <div class="panel-title">Modelos Disponibles <span class="badge" id="model-count">0 MODELOS</span></div>
      </div>
      <div class="model-grid" id="model-list">Cargando...</div>
    </div>
  </div>

  <div id="logs" style="display:none">
    <div class="panel">
      <div class="panel-head">
        <div class="panel-title">Registros Recientes <span class="badge emerald">EN VIVO</span></div>
      </div>
      <div class="log-area" id="log-box">Cargando...</div>
    </div>
  </div>

  <div id="config" style="display:none">
    <div class="panel">
      <div class="panel-head">
        <div class="panel-title">Configuracion <span class="badge">AJUSTES</span></div>
      </div>
      <div id="config-list">Cargando...</div>
    </div>
  </div>

  <div id="desktop" style="display:none">
    <div class="panel">
      <div class="panel-head">
        <div class="panel-title">Bypass de OpenCode Desktop <span class="badge">DESKTOP</span></div>
      </div>
      <p style="color:var(--text3);margin-bottom:24px;font-size:14px;line-height:1.8">Configure OpenCode Desktop para enrutar todas las llamadas API a traves del proxy oplire con manejo automatico de limites.</p>
      <div class="desktop-grid">
        <div class="desktop-tile">
          <h4>Configuracion Desktop</h4>
          <div class="val" id="desktop-config-found">Verificando...</div>
          <div class="path" id="desktop-config-path">-</div>
        </div>
        <div class="desktop-tile">
          <h4>Estado del Proxy</h4>
          <div class="val" id="desktop-is-proxied">Verificando...</div>
          <div class="path" id="desktop-api-url">-</div>
        </div>
      </div>
      <div class="actions">
        <button class="btn btn-primary" onclick="setupDesktop()">
          <svg viewBox="0 0 24 24" fill="currentColor"><path d="M9 16.17L4.83 12l-1.42 1.41L9 19 21 7l-1.41-1.41z"/></svg>
          <span>Activar Bypass</span>
        </button>
        <button class="btn btn-danger" onclick="if(confirm('Restaurar configuracion original?'))restoreDesktop()">
          <svg viewBox="0 0 24 24" fill="currentColor"><path d="M12 5V1L7 6l5 5V7c3.31 0 6 2.69 6 6s-2.69 6-6 6-6-2.69-6-6H4c0 4.42 3.58 8 8 8s8-3.58 8-8-3.58-8-8-8z"/></svg>
          <span>Restaurar Original</span>
        </button>
        <button class="btn btn-ghost" onclick="loadDesktopStatus()">
          <svg viewBox="0 0 24 24" fill="currentColor"><path d="M17.65 6.35C16.2 4.9 14.21 4 12 4c-4.42 0-7.99 3.58-7.99 8s3.57 8 7.99 8c3.73 0 6.84-2.55 7.73-6h-2.08c-.82 2.33-3.04 4-5.65 4-3.31 0-6-2.69-6-6s2.69-6 6-6c1.66 0 3.14.69 4.22 1.78L13 11h7V4l-2.35 2.35z"/></svg>
          <span>Actualizar</span>
        </button>
      </div>
    </div>
  </div>

  <div id="cache" style="display:none">
    <div class="panel">
      <div class="panel-head">
        <div class="panel-title">Carpetas de OpenCode <span class="badge cyan">SISTEMA</span></div>
      </div>
      <p style="color:var(--text3);margin-bottom:24px;font-size:14px;line-height:1.8">Deteccion automatica de carpetas de OpenCode. El sistema detecta la ubicacion raiz, configuracion, cache y datos del proyecto.</p>
      <div class="cache-grid">
        <div class="cache-tile config">
          <h4>Configuracion</h4>
          <div class="val" id="folder-config">Verificando...</div>
          <div class="path" id="folder-config-path">-</div>
        </div>
        <div class="cache-tile cache">
          <h4>Cache</h4>
          <div class="val" id="folder-cache">Verificando...</div>
          <div class="path" id="folder-cache-path">-</div>
          <div class="size" id="folder-cache-size"><span class="dot" style="background:var(--amber)"></span>Tamano: calculando...</div>
        </div>
        <div class="cache-tile data">
          <h4>Datos</h4>
          <div class="val" id="folder-data">Verificando...</div>
          <div class="path" id="folder-data-path">-</div>
          <div class="size" id="folder-data-size"><span class="dot" style="background:var(--emerald)"></span>Tamano: calculando...</div>
        </div>
      </div>
      <div class="desktop-grid">
        <div class="desktop-tile">
          <h4>Desktop App Config</h4>
          <div class="val" id="folder-desktop-config">Verificando...</div>
          <div class="path" id="folder-desktop-config-path">-</div>
        </div>
        <div class="desktop-tile">
          <h4>Raiz del Sistema</h4>
          <div class="val" id="folder-root">Verificando...</div>
          <div class="path" id="folder-root-path">-</div>
        </div>
      </div>
      <div class="actions">
        <button class="btn btn-amber" onclick="clearCache()">
          <svg viewBox="0 0 24 24" fill="currentColor"><path d="M6 19c0 1.1.9 2 2 2h8c1.1 0 2-.9 2-2V7H6v12zM19 4h-3.5l-1-1h-5l-1 1H5v2h14V4z"/></svg>
          <span>Limpiar Cache</span>
        </button>
        <button class="btn btn-danger" onclick="clearAllData()">
          <svg viewBox="0 0 24 24" fill="currentColor"><path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm1 15h-2v-2h2v2zm0-4h-2V7h2v6z"/></svg>
          <span>Borrar Todos los Datos</span>
        </button>
        <button class="btn btn-cyan" onclick="loadFolders()">
          <svg viewBox="0 0 24 24" fill="currentColor"><path d="M17.65 6.35C16.2 4.9 14.21 4 12 4c-4.42 0-7.99 3.58-7.99 8s3.57 8 7.99 8c3.73 0 6.84-2.55 7.73-6h-2.08c-.82 2.33-3.04 4-5.65 4-3.31 0-6-2.69-6-6s2.69-6 6-6c1.66 0 3.14.69 4.22 1.78L13 11h7V4l-2.35 2.35z"/></svg>
          <span>Actualizar Carpetas</span>
        </button>
      </div>
    </div>
  </div>

  <div id="programs" style="display:none">
    <div class="panel">
      <div class="panel-head">
        <div class="panel-title">Herramientas <span class="badge">UTILIDADES</span></div>
      </div>
      <p style="color:var(--text3);margin-bottom:28px;font-size:14px;line-height:1.8">Herramientas recomendadas para mejorar tu flujo de trabajo y gestionar tuneles de red.</p>
      <div class="tools-grid">
        <div class="tool-card indigo">
          <div class="tool-head">
            <div class="tool-icon"><svg viewBox="0 0 24 24"><path d="M15.5 14h-.79l-.28-.27C15.41 12.59 16 11.11 16 9.5 16 5.91 13.09 3 9.5 3S3 5.91 3 9.5 5.91 16 9.5 16c1.61 0 3.09-.59 4.23-1.57l.27.28v.79l5 4.99L20.49 19l-4.99-5zm-6 0C7.01 14 5 11.99 5 9.5S7.01 5 9.5 5 14 7.01 14 9.5 11.99 14 9.5 14z"/></svg></div>
            <h3>Everything</h3>
            <span class="tag">VOIDTOOLS</span>
          </div>
          <p>El motor de busqueda de archivos mas rapido para Windows. Encuentra cualquier archivo, carpeta o configuracion al instante en todos los discos.</p>
          <a href="https://www.voidtools.com/es-es/" target="_blank" class="tool-link">
            <svg viewBox="0 0 24 24"><path d="M19 9h-4V3H9v6H5l7 7 7-7zM5 18v2h14v-2H5z"/></svg>
            <span>Descargar Everything</span>
          </a>
        </div>
        <div class="tool-card amber">
          <div class="tool-head">
            <div class="tool-icon"><svg viewBox="0 0 24 24"><path d="M19.35 10.04C18.67 6.59 15.64 4 12 4 9.11 4 6.6 5.64 5.35 8.04 2.34 8.36 0 10.91 0 14c0 3.31 2.69 6 6 6h13c2.76 0 5-2.24 5-5 0-2.64-2.05-4.78-4.65-4.96zM17 13l-5 5-5-5h3V9h4v4h3z"/></svg></div>
            <h3>Cloudflare One Client</h3>
            <span class="tag">WARP</span>
          </div>
          <p>Cliente oficial de Cloudflare para gestion segura de tuneles WARP. Enruta tu trafico a traves de la red global de Cloudflare para privacidad y rendimiento.</p>
          <a href="https://developers.cloudflare.com/cloudflare-one/team-and-resources/devices/cloudflare-one-client/download/" target="_blank" class="tool-link">
            <svg viewBox="0 0 24 24"><path d="M19 9h-4V3H9v6H5l7 7 7-7zM5 18v2h14v-2H5z"/></svg>
            <span>Descargar Cliente</span>
          </a>
        </div>
      </div>
    </div>
  </div>
</div>

<div class="footer">
  <p>Oplire <strong>v4.0.0</strong> &mdash; Desarrollado por <strong>PolloCraft20</strong></p>
  <p style="margin-top:6px"><a href="https://github.com/PolloCraft/Oplire-OpenCode" target="_blank">github.com/PolloCraft/Oplire-OpenCode</a></p>
</div>

<div class="toast" id="toast"></div>
<script>
function showToast(m,e){
  var t=document.getElementById('toast');
  t.textContent=m;
  t.className='toast show'+(e?' error':'');
  setTimeout(function(){t.className='toast'},4000);
}
function showSection(n){
  ['overview','models','logs','config','desktop','cache','programs'].forEach(function(s){
    document.getElementById(s).style.display=s===n?'block':'none';
  });
  document.querySelectorAll('.nav button').forEach(function(b,i){
    b.className=['overview','models','logs','config','desktop','cache','programs'][i]===n?'active':'';
  });
  if(n==='models')loadModels();
  if(n==='logs')loadLogs();
  if(n==='config')loadConfig();
  if(n==='desktop')loadDesktopStatus();
  if(n==='cache')loadFolders();
}
async function refreshStatus(){
  try{
    var r=await fetch('/api/status');
    var d=await r.json();
    document.getElementById('proxy-listen').innerHTML='<code>'+d.proxy.listen+'</code>';
    document.getElementById('upstream-url').textContent=d.proxy.upstream;
    document.getElementById('max-retries').textContent=d.proxy.max_retries;
    var ws=d.warp;
    if(ws.installed){
      if(ws.connected){
        document.getElementById('warp-status').innerHTML='<span class="dot on"></span>Conectado';
        document.getElementById('warp-status').className='stat-value emerald';
      }else{
        document.getElementById('warp-status').innerHTML='<span class="dot off"></span>Desconectado';
        document.getElementById('warp-status').className='stat-value rose';
      }
      document.getElementById('warp-detail').textContent=ws.raw||'';
    }else{
      document.getElementById('warp-status').innerHTML='<span class="dot off"></span>No instalado';
      document.getElementById('warp-status').className='stat-value rose';
      document.getElementById('warp-detail').textContent='Instale Cloudflare WARP';
    }
  }catch(e){
    document.getElementById('warp-status').innerHTML='<span class="dot off"></span>Error';
    document.getElementById('warp-status').className='stat-value rose';
    document.getElementById('warp-detail').textContent=e.toString();
  }
}
async function loadModels(){
  try{
    var r=await fetch('/api/models');
    var d=await r.json();
    var models=d.data||[];
    document.getElementById('model-count').textContent=models.length+' MODELOS';
    var html='';
    models.forEach(function(m){
      var ctx=m.context_window?(m.context_window/1000).toFixed(0)+'K':'?';
      html+='<div class="model-item">';
      html+='<div class="model-id">'+(m.id||'')+'</div>';
      html+='<div class="model-name">'+(m.display_name||m.name||m.id||'')+'</div>';
      html+='<div class="model-meta"><span>'+ctx+' contexto</span></div>';
      html+='</div>';
    });
    if(!html)html='<div style="color:var(--text3);padding:48px;text-align:center;font-size:14px">No se encontraron modelos.<br>Verifique que OpenCode Zen este ejecutandose.</div>';
    document.getElementById('model-list').innerHTML=html;
  }catch(e){
    document.getElementById('model-list').innerHTML='<div style="color:var(--rose);padding:24px">Error: '+e+'</div>';
  }
}
async function loadLogs(){
  try{
    var r=await fetch('/api/logs');
    var d=await r.json();
    var logs=d.logs||[];
    var html='';
    logs.forEach(function(l){
      html+='<div class="log-row"><span class="log-time">'+new Date().toLocaleTimeString()+'</span><span class="log-msg">'+l+'</span></div>';
    });
    if(!html)html='<div style="color:var(--text3);padding:48px;text-align:center;font-size:14px">Sin registros aun</div>';
    document.getElementById('log-box').innerHTML=html;
    document.getElementById('log-box').scrollTop=0;
  }catch(e){
    document.getElementById('log-box').innerHTML='<div style="color:var(--rose);padding:24px">Error: '+e+'</div>';
  }
}
async function loadConfig(){
  try{
    var r=await fetch('/api/config');
    var d=await r.json();
    var html='';
    html+='<div class="config-item"><span class="config-key">Direccion de Escucha</span><span class="config-val">'+d.listen+'</span></div>';
    html+='<div class="config-item"><span class="config-key">URL Upstream</span><span class="config-val">'+d.upstream+'</span></div>';
    html+='<div class="config-item"><span class="config-key">Clave API</span><span class="config-val">'+(d.api_key||'ninguna')+'</span></div>';
    html+='<div class="config-item"><span class="config-key">Max. Reintentos</span><span class="config-val">'+d.max_retries+'</span></div>';
    html+='<div class="config-item"><span class="config-key">Retraso Reset WARP</span><span class="config-val">'+d.warp_delay_ms+'ms</span></div>';
    if(d.free_models&&d.free_models.length){
      html+='<div class="config-item"><span class="config-key">Modelos Gratis</span><span class="config-val">'+d.free_models.length+' disponibles</span></div>';
    }
    document.getElementById('config-list').innerHTML=html;
  }catch(e){
    document.getElementById('config-list').innerHTML='<div style="color:var(--rose);padding:24px">Error: '+e+'</div>';
  }
}
async function loadFolders(){
  try{
    var r=await fetch('/api/opencode-folders');
    var d=await r.json();
    document.getElementById('folder-config').innerHTML=d.config_exists?'<span class="dot on"></span>Encontrado':'<span class="dot off"></span>No encontrado';
    document.getElementById('folder-config-path').textContent=d.config||'No detectado';
    document.getElementById('folder-cache').innerHTML=d.cache_exists?'<span class="dot on"></span>Encontrado':'<span class="dot off"></span>No encontrado';
    document.getElementById('folder-cache-path').textContent=d.cache||'No detectado';
    document.getElementById('folder-cache-size').innerHTML='<span class="dot" style="background:var(--amber)"></span>Tamano: '+(d.cache_size_human||'0 B');
    document.getElementById('folder-data').innerHTML=d.data_exists?'<span class="dot on"></span>Encontrado':'<span class="dot off"></span>No encontrado';
    document.getElementById('folder-data-path').textContent=d.data||'No detectado';
    document.getElementById('folder-data-size').innerHTML='<span class="dot" style="background:var(--emerald)"></span>Tamano: '+(d.data_size_human||'0 B');
    document.getElementById('folder-desktop-config').innerHTML=d.desktop_config_exists?'<span class="dot on"></span>Encontrado':'<span class="dot off"></span>No encontrado';
    document.getElementById('folder-desktop-config-path').textContent=d.desktop_config||'No detectado';
    document.getElementById('folder-root').innerHTML=d.root?'<span class="dot on"></span>Encontrado':'<span class="dot off"></span>No encontrado';
    document.getElementById('folder-root-path').textContent=d.root||'No detectado';
  }catch(e){
    document.getElementById('folder-config').innerHTML='<span class="dot off"></span>Error';
    document.getElementById('folder-config-path').textContent=e.toString();
  }
}
async function clearCache(){
  if(!confirm('Limpiar la cache de OpenCode?\n\nEsto eliminara archivos temporales pero NO su configuracion ni datos.'))return;
  try{
    showToast('Limpiando cache...');
    var r=await fetch('/api/clear-cache',{method:'POST'});
    var d=await r.json();
    if(d.success){
      showToast(d.message||'Cache limpiado correctamente!');
      loadFolders();
    }else{
      showToast('Error: '+(d.error||'Desconocido'),true);
    }
  }catch(e){showToast('Error: '+e,true)}
}
async function clearAllData(){
  if(!confirm('ATENCION: Borrar TODOS los datos de OpenCode?\n\nEsto eliminara:\n- Cache\n- Datos\n- Configuracion local\n\nNO se eliminara el config.json de Desktop.'))return;
  try{
    showToast('Borrando todos los datos...');
    var r=await fetch('/api/clear-all-data',{method:'POST'});
    var d=await r.json();
    if(d.success){
      showToast(d.message||'Datos eliminados!');
      loadFolders();
    }else{
      showToast('Error: '+(d.error||'Desconocido'),true);
    }
  }catch(e){showToast('Error: '+e,true)}
}
async function resetIP(){
  try{
    showToast('Reseteando IP de WARP...');
    var r=await fetch('/api/reset-ip',{method:'POST'});
    var d=await r.json();
    if(d.success){showToast('IP reseteada exitosamente!')}
    else{showToast('Error al resetear: '+(d.error||'Desconocido'),true)}
  }catch(e){showToast('Error al resetear: '+e,true)}
}
async function restoreIP(){
  try{
    showToast('Verificando estado de red...');
    var statusR=await fetch('/api/network/status');
    var statusD=await statusR.json();
    var backupInfo='No se encontro respaldo previo.';
    if(statusD.backup_exists&&statusD.backup){
      var b=statusD.backup;
      var adapterCount=b.adapters?b.adapters.length:0;
      var publicIp=b.public_ip||'desconocido';
      var warpActive=b.warp_active?'Si':'No';
      backupInfo='Respaldo encontrado del '+new Date(b.timestamp*1000).toLocaleString()+'.\n\nAdaptadores: '+adapterCount+'\nIP Publica: '+publicIp+'\nWARP activo: '+warpActive+'\n\nLa restauracion:\n1. Desconectara WARP completamente\n2. Eliminara el registro de WARP\n3. Restaurara la configuracion de red desde el respaldo\n4. Verificara la restauracion';
    }
    var currentInfo='';
    if(statusD.current){
      var c=statusD.current;
      var currentIp='desconocido';
      if(c.adapters){
        for(var i=0;i<c.adapters.length;i++){
          if(c.adapters[i].ipv4_address){currentIp=c.adapters[i].ipv4_address;break;}
        }
      }
      currentInfo='\n\nEstado actual:\nIP Publica: '+(c.public_ip||'desconocido')+'\nIP Local: '+currentIp;
    }
    var confirmed=confirm('Restaurar configuracion de red anterior?\n\n'+backupInfo+currentInfo+'\n\nProceder con la restauracion?');
    if(!confirmed){return;}
    showToast('Restaurando configuracion de red...');
    var r=await fetch('/api/restore-ip',{method:'POST'});
    var d=await r.json();
    if(d.success){
      var result=d.result||{};
      var msg=result.message||'Restauracion completada!';
      if(result.network_restoration){
        var nr=result.network_restoration;
        if(nr.restored_items&&nr.restored_items.length>0){
          msg+='\n\nRestaurado: '+nr.restored_items.join(', ');
        }
        if(nr.warnings&&nr.warnings.length>0){
          msg+='\n\nAdvertencias: '+nr.warnings.join(', ');
        }
        if(nr.failed_items&&nr.failed_items.length>0){
          msg+='\n\nFallido: '+nr.failed_items.join(', ');
        }
      }
      showToast(msg);
      refreshStatus();
    }
    else{showToast('Error al restaurar: '+(d.error||'Desconocido'),true)}
  }catch(e){showToast('Error al restaurar: '+e,true)}
}
async function loadDesktopStatus(){
  try{
    var r=await fetch('/api/desktop-status');
    var d=await r.json();
    document.getElementById('desktop-config-found').innerHTML=d.config_found?'<span class="dot on"></span>Encontrado':'<span class="dot off"></span>No encontrado';
    document.getElementById('desktop-config-path').textContent=d.config_path;
    document.getElementById('desktop-is-proxied').innerHTML=d.is_proxied?'<span class="dot on"></span>Activo':'<span class="dot off"></span>Inactivo';
    document.getElementById('desktop-api-url').textContent=d.api_base_url||'No configurado';
  }catch(e){
    document.getElementById('desktop-config-found').innerHTML='<span class="dot off"></span>Error';
    document.getElementById('desktop-config-path').textContent=e.toString();
  }
}
async function setupDesktop(){
  try{
    showToast('Configurando Desktop...');
    var r=await fetch('/api/setup-desktop',{method:'POST'});
    var d=await r.json();
    if(d.success){showToast('Desktop configurado! Reinicie la app.');loadDesktopStatus()}
    else{showToast('Error: '+(d.error||'Desconocido'),true)}
  }catch(e){showToast('Error: '+e,true)}
}
async function restoreDesktop(){
  try{
    showToast('Restaurando configuracion...');
    var r=await fetch('/api/restore-desktop',{method:'POST'});
    var d=await r.json();
    if(d.success){showToast('Configuracion restaurada! Reinicie Desktop.');loadDesktopStatus()}
    else{showToast('Error: '+(d.error||'Desconocido'),true)}
  }catch(e){showToast('Error: '+e,true)}
}
refreshStatus();
setInterval(refreshStatus,10000);
</script>
</body>
</html>"#;
