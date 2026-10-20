use std::path::PathBuf;
use std::sync::atomic::{AtomicU32, Ordering};
use std::sync::Arc;
use std::time::{Duration, Instant, SystemTime, UNIX_EPOCH};
use tokio::fs;
use tokio::process::Command;
use tokio::sync::Mutex;
use tracing::{error, info, warn};

use crate::network::NetworkManager;

static RESET_IN_PROGRESS: Mutex<()> = Mutex::const_new(());

pub struct WarpResolver {
    pub max_retries: u32,
    pub reset_delay_ms: u64,
    reset_count: AtomicU32,
    last_reset: Mutex<Option<Instant>>,
    state_path: PathBuf,
    original_ip_path: PathBuf,
    network_manager: NetworkManager,
}

#[derive(serde::Serialize, serde::Deserialize, Clone, Debug)]
pub struct OriginalIpInfo {
    pub ip: String,
    pub captured_at: u64,
    pub source: String,
}

pub struct WarpState {
    last_ip: String,
    last_reset_timestamp: u64,
    total_resets: u32,
    consecutive_429: u32,
}

impl WarpResolver {
    pub fn new(max_retries: u32, reset_delay_ms: u64) -> Arc<Self> {
        let state_path = Self::get_state_path();
        let original_ip_path = Self::get_original_ip_path();
        let network_manager = NetworkManager::new();
        Arc::new(Self {
            max_retries,
            reset_delay_ms,
            reset_count: AtomicU32::new(0),
            last_reset: Mutex::new(None),
            state_path,
            original_ip_path,
            network_manager,
        })
    }

    pub fn get_network_manager(&self) -> &NetworkManager {
        &self.network_manager
    }

    fn get_state_path() -> PathBuf {
        let base = Self::get_data_dir();
        base.join("warp_state.json")
    }

    fn get_original_ip_path() -> PathBuf {
        let base = Self::get_data_dir();
        base.join("original_ip.json")
    }

    fn get_data_dir() -> PathBuf {
        if cfg!(target_os = "windows") {
            std::env::var("LOCALAPPDATA")
                .map(PathBuf::from)
                .unwrap_or_else(|_| PathBuf::from("."))
                .join("oplire")
        } else if cfg!(target_os = "macos") {
            std::env::var("HOME")
                .map(PathBuf::from)
                .unwrap_or_else(|_| PathBuf::from("."))
                .join("Library/Application Support/oplire")
        } else {
            std::env::var("XDG_DATA_HOME")
                .map(PathBuf::from)
                .unwrap_or_else(|_| {
                    std::env::var("HOME")
                        .map(PathBuf::from)
                        .unwrap_or_else(|_| PathBuf::from("."))
                        .join(".local/share")
                })
                .join("oplire")
        }
    }

    pub fn get_reset_count(&self) -> u32 {
        self.reset_count.load(Ordering::Relaxed)
    }

    pub async fn get_real_ip() -> Result<String, String> {
        let client = reqwest::Client::builder()
            .timeout(Duration::from_secs(10))
            .build()
            .map_err(|e| format!("Failed to create client: {}", e))?;

        let services = [
            "https://api.ipify.org?format=json",
            "https://httpbin.org/ip",
            "https://ifconfig.me/ip",
            "https://icanhazip.com",
        ];

        for url in &services {
            match client.get(*url).send().await {
                Ok(resp) => {
                    if resp.status().is_success() {
                        let body = resp.text().await.unwrap_or_default();

                        if let Ok(json) = serde_json::from_str::<serde_json::Value>(&body) {
                            if let Some(ip) = json.get("ip").and_then(|v| v.as_str()) {
                                return Ok(ip.to_string());
                            }
                            if let Some(origin) = json.get("origin").and_then(|v| v.as_str()) {
                                return Ok(origin.to_string());
                            }
                        }

                        let ip = body.trim().to_string();
                        if !ip.is_empty() && ip.chars().any(|c| c.is_ascii_digit()) {
                            return Ok(ip);
                        }
                    }
                }
                Err(_) => continue,
            }
        }

        Err("Could not determine real IP from any service".to_string())
    }

    pub async fn capture_original_ip(&self) -> Result<OriginalIpInfo, String> {
        if let Ok(content) = fs::read_to_string(&self.original_ip_path).await {
            if let Ok(info) = serde_json::from_str::<OriginalIpInfo>(&content) {
                if !info.ip.is_empty() {
                    info!("Original IP already captured: {}", info.ip);
                    return Ok(info);
                }
            }
        }

        let ip = Self::get_real_ip().await?;
        let info = OriginalIpInfo {
            ip: ip.clone(),
            captured_at: SystemTime::now()
                .duration_since(UNIX_EPOCH)
                .map(|d| d.as_secs())
                .unwrap_or(0),
            source: "captured_before_warp".to_string(),
        };

        if let Some(parent) = self.original_ip_path.parent() {
            fs::create_dir_all(parent)
                .await
                .map_err(|e| format!("Failed to create dir: {}", e))?;
        }

        let json = serde_json::to_string_pretty(&info)
            .map_err(|e| e.to_string())?;
        fs::write(&self.original_ip_path, json)
            .await
            .map_err(|e| format!("Failed to save original IP: {}", e))?;

        info!("Original IP captured: {}", ip);
        Ok(info)
    }

    pub async fn get_saved_original_ip(&self) -> Option<OriginalIpInfo> {
        let content = fs::read_to_string(&self.original_ip_path).await.ok()?;
        serde_json::from_str(&content).ok()
    }

    pub async fn restore_original_ip(self: &Arc<Self>) -> Result<String, String> {
        info!("[RESTORE] Starting IP restoration process...");

        let original_info = self.get_saved_original_ip().await;
        let original_ip = original_info.as_ref().map(|i| i.ip.as_str()).unwrap_or("unknown");

        info!("[RESTORE] Original IP to restore: {}", original_ip);

        info!("[RESTORE] Step 1/5: Disconnecting WARP...");
        let _ = warp_cmd(&["disconnect"]).await;
        sleep_ms(1000).await;

        info!("[RESTORE] Step 2/5: Deleting WARP registration...");
        let _ = warp_cmd(&["registration", "delete"]).await;
        sleep_ms(500).await;

        if cfg!(target_os = "linux") {
            info!("[RESTORE] Step 3/5: Stopping warp-svc...");
            let _ = sudo_cmd("systemctl stop warp-svc").await;
            sleep_ms(500).await;

            info!("[RESTORE] Step 3b/5: Clearing WARP state...");
            let _ = sudo_cmd("rm -rf /var/lib/cloudflare-warp/*").await;
            sleep_ms(500).await;

            info!("[RESTORE] Step 3c/5: Starting warp-svc...");
            let _ = sudo_cmd("systemctl start warp-svc").await;
            sleep_ms(2000).await;
        } else {
            info!("[RESTORE] Step 3/5: Waiting for network reset...");
            sleep_ms(2000).await;
        }

        info!("[RESTORE] Step 4/5: Restoring full network configuration from backup...");
        let restore_result = self.network_manager.restore_network().await;

        info!("[RESTORE] Step 5/5: Verifying current IP...");
        let current_ip = Self::get_real_ip().await.unwrap_or_else(|_| "unknown".to_string());

        self.reset_count.store(0, Ordering::SeqCst);

        let now = SystemTime::now()
            .duration_since(UNIX_EPOCH)
            .map(|d| d.as_secs())
            .unwrap_or(0);

        let state = WarpState {
            last_ip: current_ip.clone(),
            last_reset_timestamp: now,
            total_resets: 0,
            consecutive_429: 0,
        };
        let _ = self.save_state(&state).await;

        match restore_result {
            Ok(result) => {
                let ip_matches = if original_ip != "unknown" && current_ip != "unknown" {
                    original_ip == current_ip
                } else {
                    false
                };

                let response = serde_json::json!({
                    "success": result.success,
                    "original_ip": original_ip,
                    "current_ip": current_ip,
                    "ip_matches": ip_matches,
                    "network_restoration": {
                        "status": result.status,
                        "restored_items": result.restored_items,
                        "failed_items": result.failed_items,
                        "warnings": result.warnings,
                        "verification_passed": result.verification_passed,
                    },
                    "message": if result.success {
                        format!("Full restoration completed. IP: {} → {}. {} items restored.", original_ip, current_ip, result.restored_items.len())
                    } else if result.restored_items.is_empty() {
                        format!("WARP disconnected. Current IP: {}. Network restoration: {}", current_ip, result.message)
                    } else {
                        format!("Partial restoration. IP: {}. {}", current_ip, result.message)
                    }
                });

                info!("[RESTORE] Restoration complete: {}", response);
                Ok(response.to_string())
            }
            Err(e) => {
                let response = serde_json::json!({
                    "success": false,
                    "original_ip": original_ip,
                    "current_ip": current_ip,
                    "error": e,
                    "message": format!("WARP disconnected but network restoration failed: {}. Current IP: {}", e, current_ip)
                });

                warn!("[RESTORE] Restoration partially failed: {}", response);
                Ok(response.to_string())
            }
        }
    }

    pub async fn handle_429(self: &Arc<Self>, retry_count: u32) -> bool {
        if retry_count >= self.max_retries {
            warn!(
                "Max retry attempts ({}) reached, giving up",
                self.max_retries
            );
            return false;
        }

        let _guard = match RESET_IN_PROGRESS.try_lock() {
            Ok(g) => g,
            Err(_) => {
                info!("WARP reset already in progress, waiting...");
                tokio::time::sleep(Duration::from_millis(self.reset_delay_ms)).await;
                return true;
            }
        };

        let _ = self.capture_original_ip().await;

        info!("[NETWORK] Capturing network state before WARP rotation");
        self.network_manager.init().await;
        match self.network_manager.capture_snapshot("warp_rotation").await {
            Ok(snapshot) => {
                info!(
                    "[NETWORK] Network state captured: {} adapters, public_ip={:?}",
                    snapshot.adapters.len(),
                    snapshot.public_ip
                );
            }
            Err(e) => {
                warn!("Failed to capture network state: {}", e);
            }
        }

        let count = self.reset_count.fetch_add(1, Ordering::SeqCst) + 1;
        info!(
            "HTTP 429 detected (reset #{}). Starting ephemeral WARP rotation...",
            count
        );

        if let Err(e) = self.reset_warp().await {
            error!("WARP reset failed: {}", e);
            self.reset_count.fetch_sub(1, Ordering::SeqCst);
            return false;
        }

        {
            let mut last = self.last_reset.lock().await;
            *last = Some(Instant::now());
        }

        let state = WarpState {
            last_ip: self.get_current_ip().await.unwrap_or_default(),
            last_reset_timestamp: SystemTime::now()
                .duration_since(UNIX_EPOCH)
                .map(|d| d.as_secs())
                .unwrap_or(0),
            total_resets: self.reset_count.load(Ordering::Relaxed),
            consecutive_429: retry_count + 1,
        };
        let _ = self.save_state(&state).await;

        info!("WARP reset complete. Disconnecting WARP tunnel...");
        tokio::time::sleep(Duration::from_millis(1500)).await;
        let _ = warp_cmd(&["disconnect"]).await;
        info!("WARP disconnected. IP rotation is persistent - no tunnel needed.");

        true
    }

    pub async fn reset_warp(&self) -> Result<(), String> {
        if cfg!(target_os = "windows") {
            self.reset_warp_windows().await
        } else if cfg!(target_os = "macos") {
            self.reset_warp_macos().await
        } else {
            self.reset_warp_linux().await
        }
    }

    async fn reset_warp_windows(&self) -> Result<(), String> {
        info!("[WARP] Step 1/5: Check current status");
        let _ = warp_cmd(&["status"]).await;

        info!("[WARP] Step 2/5: Disconnect");
        let _ = warp_cmd(&["disconnect"]).await;
        sleep_ms(800).await;

        info!("[WARP] Step 3/5: Delete old registration");
        let _ = warp_cmd(&["registration", "delete"]).await;
        sleep_ms(500).await;

        info!("[WARP] Step 4/5: Create new registration");
        warp_cmd(&["registration", "new"]).await.map_err(|e| {
            format!(
                "Registration failed: {}. Try: warp-cli registration delete && warp-cli registration new",
                e
            )
        })?;
        sleep_ms(1000).await;

        info!("[WARP] Step 5/5: Connect");
        warp_cmd(&["connect"]).await?;

        info!("[WARP] New IP assigned successfully");
        Ok(())
    }

    async fn reset_warp_linux(&self) -> Result<(), String> {
        info!("[WARP] Step 1/6: Disconnect");
        warp_cmd(&["disconnect"]).await?;
        sleep_ms(800).await;

        info!("[WARP] Step 2/6: Stop warp-svc");
        let _ = sudo_cmd("systemctl stop warp-svc").await;
        sleep_ms(500).await;

        info!("[WARP] Step 3/6: Clear warp state");
        let _ = sudo_cmd("rm -rf /var/lib/cloudflare-warp/*").await;
        sleep_ms(500).await;

        info!("[WARP] Step 4/6: Start warp-svc");
        let _ = sudo_cmd("systemctl start warp-svc").await;
        sleep_ms(2500).await;

        info!("[WARP] Step 5/6: Create new registration");
        let _ = warp_cmd(&["registration", "delete"]).await;
        sleep_ms(500).await;
        warp_cmd(&["registration", "new"]).await?;
        sleep_ms(1000).await;

        info!("[WARP] Step 6/6: Connect");
        warp_cmd(&["connect"]).await?;

        info!("[WARP] New IP assigned successfully");
        Ok(())
    }

    async fn reset_warp_macos(&self) -> Result<(), String> {
        info!("[WARP] Disconnect");
        warp_cmd(&["disconnect"]).await?;
        sleep_ms(800).await;

        info!("[WARP] Delete old registration");
        let _ = warp_cmd(&["registration", "delete"]).await;
        sleep_ms(500).await;

        info!("[WARP] Create new registration");
        warp_cmd(&["registration", "new"]).await?;
        sleep_ms(1000).await;

        info!("[WARP] Connect");
        warp_cmd(&["connect"]).await?;

        info!("[WARP] New IP assigned successfully");
        Ok(())
    }

    async fn get_current_ip(&self) -> Result<String, String> {
        let output = warp_cmd(&["settings"]).await?;
        for line in output.lines() {
            if let Some(ip) = line.strip_prefix("Speaker: ") {
                return Ok(ip.trim().to_string());
            }
        }
        Ok(String::new())
    }

    async fn save_state(&self, state: &WarpState) -> Result<(), String> {
        if let Some(parent) = self.state_path.parent() {
            fs::create_dir_all(parent)
                .await
                .map_err(|e| format!("Failed to create state dir: {}", e))?;
        }

        let json = serde_json::json!({
            "last_ip": state.last_ip,
            "last_reset_timestamp": state.last_reset_timestamp,
            "total_resets": state.total_resets,
            "consecutive_429": state.consecutive_429,
        });

        let content =
            serde_json::to_string_pretty(&json).map_err(|e| e.to_string())?;
        fs::write(&self.state_path, content)
            .await
            .map_err(|e| format!("Failed to save state: {}", e))?;

        Ok(())
    }

    pub async fn load_state(&self) -> Option<WarpState> {
        let content = fs::read_to_string(&self.state_path)
            .await
            .ok()?;
        let json: serde_json::Value = serde_json::from_str(&content).ok()?;

        Some(WarpState {
            last_ip: json.get("last_ip")?.as_str()?.to_string(),
            last_reset_timestamp: json
                .get("last_reset_timestamp")?
                .as_u64()?,
            total_resets: json.get("total_resets")?.as_u64()? as u32,
            consecutive_429: json
                .get("consecutive_429")?
                .as_u64()? as u32,
        })
    }

    pub async fn get_last_reset_info(&self) -> Option<(String, u64, u32)> {
        let state = self.load_state().await?;
        Some((state.last_ip, state.last_reset_timestamp, state.total_resets))
    }

    pub async fn is_rate_limited() -> bool {
        let client = reqwest::Client::builder()
            .timeout(Duration::from_secs(5))
            .build()
            .unwrap_or_default();

        let url = "http://localhost:3000/v1/models";
        match client.get(url).send().await {
            Ok(resp) => resp.status().as_u16() == 429,
            Err(_) => false,
        }
    }

    pub async fn full_cleanup(self: &Arc<Self>) -> Result<(), String> {
        info!("[WARP] Performing full cleanup...");

        info!("[WARP] Disconnecting...");
        let _ = warp_cmd(&["disconnect"]).await;
        sleep_ms(500).await;

        info!("[WARP] Deleting registration...");
        let _ = warp_cmd(&["registration", "delete"]).await;
        sleep_ms(300).await;

        if cfg!(target_os = "linux") {
            info!("[WARP] Stopping warp-svc...");
            let _ = sudo_cmd("systemctl stop warp-svc").await;
            sleep_ms(300).await;

            info!("[WARP] Clearing warp state...");
            let _ = sudo_cmd("rm -rf /var/lib/cloudflare-warp/*").await;
            sleep_ms(300).await;

            info!("[WARP] Starting warp-svc...");
            let _ = sudo_cmd("systemctl start warp-svc").await;
            sleep_ms(1500).await;
        }

        self.reset_count.store(0, Ordering::SeqCst);

        info!("[WARP] Full cleanup complete");
        Ok(())
    }
}

async fn warp_cmd(args: &[&str]) -> Result<String, String> {
    let output = Command::new("warp-cli")
        .args(args)
        .output()
        .await
        .map_err(|e| format!("warp-cli not found: {}", e))?;

    let stdout = String::from_utf8_lossy(&output.stdout).to_string();
    let stderr = String::from_utf8_lossy(&output.stderr).to_string();

    if output.status.success() {
        Ok(stdout.trim().to_string())
    } else {
        let msg = if stderr.is_empty() {
            &stdout
        } else {
            &stderr
        };
        Err(format!("warp-cli {:?}: {}", args, msg.trim()))
    }
}

async fn sudo_cmd(cmd: &str) -> Result<String, String> {
    let output = Command::new("sudo")
        .arg("-n")
        .arg("sh")
        .arg("-c")
        .arg(cmd)
        .output()
        .await
        .map_err(|e| format!("sudo failed: {}", e))?;

    if output.status.success() {
        Ok(String::from_utf8_lossy(&output.stdout).to_string())
    } else {
        Err(format!("sudo {} failed", cmd))
    }
}

async fn sleep_ms(ms: u64) {
    tokio::time::sleep(Duration::from_millis(ms)).await;
}
