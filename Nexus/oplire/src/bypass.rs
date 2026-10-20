use std::fs;
use std::path::PathBuf;
use std::time::{SystemTime, UNIX_EPOCH};
use tracing::{info, warn};

const BYPASS_MARKER: &str = "__oplire_bypass_active__";

pub struct DesktopBypass {
    pub config_path: PathBuf,
    pub backup_path: PathBuf,
    pub state_path: PathBuf,
}

pub struct BypassStatus {
    pub config_found: bool,
    pub config_path: String,
    pub is_proxied: bool,
    pub api_base_url: String,
    pub api_key: String,
    pub backup_exists: bool,
    pub bypass_active: bool,
    pub last_verified: Option<u64>,
}

#[derive(serde::Serialize, serde::Deserialize)]
struct BypassState {
    enabled: bool,
    proxy_addr: String,
    enabled_at: u64,
    last_verified: Option<u64>,
    config_hash: Option<String>,
}

impl DesktopBypass {
    pub fn new() -> Self {
        let config_path = find_opencode_desktop_config();
        let backup_path = config_path.with_extension("json.bak");
        let state_path = Self::get_state_path();
        Self {
            config_path,
            backup_path,
            state_path,
        }
    }

    fn get_state_path() -> PathBuf {
        let base = if cfg!(target_os = "windows") {
            std::env::var("LOCALAPPDATA")
                .map(std::path::PathBuf::from)
                .unwrap_or_else(|_| std::path::PathBuf::from("."))
                .join("oplire")
        } else if cfg!(target_os = "macos") {
            std::env::var("HOME")
                .map(std::path::PathBuf::from)
                .unwrap_or_else(|_| std::path::PathBuf::from("."))
                .join("Library/Application Support/oplire")
        } else {
            std::env::var("XDG_DATA_HOME")
                .map(std::path::PathBuf::from)
                .unwrap_or_else(|_| {
                    std::env::var("HOME")
                        .map(std::path::PathBuf::from)
                        .unwrap_or_else(|_| std::path::PathBuf::from("."))
                        .join(".local/share")
                })
                .join("oplire")
        };
        base.join("bypass_state.json")
    }

    pub fn status(&self) -> BypassStatus {
        let config_found = self.config_path.exists();
        let mut api_base_url = String::new();
        let mut api_key = String::new();
        let mut is_proxied = false;

        if config_found {
            if let Ok(content) = fs::read_to_string(&self.config_path) {
                if let Ok(config) = serde_json::from_str::<serde_json::Value>(&content) {
                    if let Some(api) = config.get("api") {
                        api_base_url = api
                            .get("base_url")
                            .and_then(|v| v.as_str())
                            .unwrap_or("")
                            .to_string();
                        api_key = api
                            .get("key")
                            .and_then(|v| v.as_str())
                            .unwrap_or("")
                            .to_string();
                        is_proxied = api_base_url.contains("127.0.0.1:8080")
                            || api_base_url.contains("localhost:8080");
                    }

                    if let Some(marker) = config.get(BYPASS_MARKER) {
                        if marker.as_bool().unwrap_or(false) {
                            is_proxied = true;
                        }
                    }
                }
            }
        }

        let state = self.load_state();
        let bypass_active = state.as_ref().map(|s| s.enabled).unwrap_or(false);

        BypassStatus {
            config_found,
            config_path: self.config_path.display().to_string(),
            is_proxied,
            api_base_url,
            api_key,
            backup_exists: self.backup_path.exists(),
            bypass_active: bypass_active || is_proxied,
            last_verified: state.as_ref().and_then(|s| s.last_verified),
        }
    }

    pub fn enable(&self, listen_addr: &str) -> Result<String, String> {
        let dir = self
            .config_path
            .parent()
            .ok_or("Cannot get config parent directory")?;
        fs::create_dir_all(dir).map_err(|e| format!("Failed to create config dir: {}", e))?;

        let mut config: serde_json::Value = if self.config_path.exists() {
            let content =
                fs::read_to_string(&self.config_path).map_err(|e| e.to_string())?;
            serde_json::from_str(&content).unwrap_or(serde_json::json!({}))
        } else {
            serde_json::json!({})
        };

        if self.config_path.exists() {
            let backup_dir = self.backup_path.parent().unwrap_or(dir);
            fs::create_dir_all(backup_dir).ok();

            let timestamp = SystemTime::now()
                .duration_since(UNIX_EPOCH)
                .map(|d| d.as_secs())
                .unwrap_or(0);
            let timestamped_backup = self
                .backup_path
                .with_file_name(format!("{}.{}.bak", "config", timestamp));

            fs::copy(&self.config_path, &timestamped_backup)
                .map_err(|e| format!("Backup failed: {}", e))?;
            fs::copy(&self.config_path, &self.backup_path)
                .map_err(|e| format!("Backup failed: {}", e))?;
            info!("Backups created: {} and {}", self.backup_path.display(), timestamped_backup.display());
        }

        if config.get("api").is_none() {
            config["api"] = serde_json::json!({});
        }

        let proxy_url = format!("http://{}", listen_addr);
        config["api"]["base_url"] = serde_json::Value::String(proxy_url.clone());
        config["api"]["key"] =
            serde_json::Value::String("oplire-proxy-key".to_string());

        config[BYPASS_MARKER] = serde_json::Value::Bool(true);

        let pretty =
            serde_json::to_string_pretty(&config).map_err(|e| e.to_string())?;
        fs::write(&self.config_path, pretty).map_err(|e| e.to_string())?;

        let now = SystemTime::now()
            .duration_since(UNIX_EPOCH)
            .map(|d| d.as_secs())
            .unwrap_or(0);

        let state = BypassState {
            enabled: true,
            proxy_addr: listen_addr.to_string(),
            enabled_at: now,
            last_verified: Some(now),
            config_hash: self.compute_config_hash(),
        };
        let _ = self.save_state(&state);

        info!(
            "OpenCode Desktop configured to use proxy at {}",
            proxy_url
        );

        Ok(format!(
            "OpenCode Desktop configured successfully.\n\
             Config: {}\n\
             API Base URL: {}\n\
             API Key: oplire-proxy-key\n\
             Backup: {}\n\
             Bypass state: persisted\n\
             \n\
             Restart OpenCode Desktop for changes to take effect.",
            self.config_path.display(),
            proxy_url,
            self.backup_path.display()
        ))
    }

    pub fn disable(&self) -> Result<String, String> {
        if !self.backup_path.exists() {
            if self.config_path.exists() {
                let mut config: serde_json::Value = serde_json::from_str(
                    &fs::read_to_string(&self.config_path)
                        .map_err(|e| e.to_string())?,
                )
                .unwrap_or(serde_json::json!({}));

                if let Some(api) = config.get_mut("api") {
                    if let Some(obj) = api.as_object_mut() {
                        obj.remove("base_url");
                        obj.remove("key");
                    }
                }

                config.as_object_mut().map(|o| o.remove(BYPASS_MARKER));

                let pretty =
                    serde_json::to_string_pretty(&config).map_err(|e| e.to_string())?;
                fs::write(&self.config_path, pretty)
                    .map_err(|e| e.to_string())?;

                self.clear_state();
                return Ok(
                    "Proxy settings removed from OpenCode Desktop config.".to_string()
                );
            }
            return Err("No backup found and no config to restore.".to_string());
        }

        fs::copy(&self.backup_path, &self.config_path)
            .map_err(|e| format!("Restore failed: {}", e))?;

        if self.config_path.exists() {
            let mut config: serde_json::Value = serde_json::from_str(
                &fs::read_to_string(&self.config_path)
                    .map_err(|e| e.to_string())?,
            )
            .unwrap_or(serde_json::json!({}));
            config.as_object_mut().map(|o| o.remove(BYPASS_MARKER));
            let pretty =
                serde_json::to_string_pretty(&config).map_err(|e| e.to_string())?;
            fs::write(&self.config_path, pretty)
                .map_err(|e| e.to_string())?;
        }

        fs::remove_file(&self.backup_path).ok();
        self.clear_state();

        info!("OpenCode Desktop config restored from backup");

        Ok(format!(
            "OpenCode Desktop configuration restored.\n\
             Config: {}\n\
             \n\
             Restart OpenCode Desktop for changes to take effect.",
            self.config_path.display()
        ))
    }

    pub fn verify_and_reapply(&self, listen_addr: &str) -> Result<bool, String> {
        let state = match self.load_state() {
            Some(s) => s,
            None => return Ok(false),
        };

        if !state.enabled {
            return Ok(false);
        }

        let current_hash = self.compute_config_hash();
        let hash_changed = current_hash != state.config_hash;

        let status = self.status();
        let needs_reapply = !status.is_proxied || hash_changed;

        if needs_reapply {
            info!("Bypass needs reapplication (proxied={}, hash_changed={})",
                status.is_proxied, hash_changed);

            if hash_changed {
                warn!("Config file was modified externally, reapplying bypass");
            }

            self.enable(listen_addr)?;

            let mut updated_state = state;
            updated_state.last_verified = Some(
                SystemTime::now()
                    .duration_since(UNIX_EPOCH)
                    .map(|d| d.as_secs())
                    .unwrap_or(0),
            );
            updated_state.config_hash = self.compute_config_hash();
            let _ = self.save_state(&updated_state);

            return Ok(true);
        }

        let mut updated_state = state;
        updated_state.last_verified = Some(
            SystemTime::now()
                .duration_since(UNIX_EPOCH)
                .map(|d| d.as_secs())
                .unwrap_or(0),
        );
        let _ = self.save_state(&updated_state);

        Ok(false)
    }

    fn compute_config_hash(&self) -> Option<String> {
        let content = fs::read_to_string(&self.config_path).ok()?;
        let mut hash: u64 = 0;
        for byte in content.bytes() {
            hash = hash.wrapping_mul(31).wrapping_add(byte as u64);
        }
        Some(format!("{:016x}", hash))
    }

    fn save_state(&self, state: &BypassState) -> Result<(), String> {
        if let Some(parent) = self.state_path.parent() {
            fs::create_dir_all(parent).map_err(|e| e.to_string())?;
        }
        let json =
            serde_json::to_string_pretty(state).map_err(|e| e.to_string())?;
        fs::write(&self.state_path, json).map_err(|e| e.to_string())?;
        Ok(())
    }

    fn load_state(&self) -> Option<BypassState> {
        let content = fs::read_to_string(&self.state_path).ok()?;
        serde_json::from_str(&content).ok()
    }

    fn clear_state(&self) {
        let _ = fs::remove_file(&self.state_path);
    }
}

pub fn find_opencode_desktop_config() -> PathBuf {
    let mut candidates: Vec<PathBuf> = Vec::new();

    if let Ok(appdata) = std::env::var("APPDATA") {
        let mut p = PathBuf::from(&appdata);
        p.push("opencode");
        p.push("config.json");
        candidates.push(p);
    }

    if let Ok(localappdata) = std::env::var("LOCALAPPDATA") {
        let mut p = PathBuf::from(&localappdata);
        p.push("opencode");
        p.push("config.json");
        candidates.push(p);
    }

    if let Ok(home) = std::env::var("USERPROFILE") {
        let mut p = PathBuf::from(home);
        p.push(".opencode");
        p.push("config.json");
        candidates.push(p);
    }

    if let Ok(home) = std::env::var("HOME") {
        let mut p = PathBuf::from(&home);
        p.push(".opencode");
        p.push("config.json");
        candidates.push(p);

        let mut p2 = PathBuf::from(&home);
        p2.push(".config");
        p2.push("opencode");
        p2.push("config.json");
        candidates.push(p2);

        let mut p3 = PathBuf::from(&home);
        p3.push("Library");
        p3.push("Application Support");
        p3.push("opencode");
        p3.push("config.json");
        candidates.push(p3);
    }

    if let Ok(xdg) = std::env::var("XDG_CONFIG_HOME") {
        let mut p = PathBuf::from(xdg);
        p.push("opencode");
        p.push("config.json");
        candidates.push(p);
    }

    for c in &candidates {
        if c.exists() {
            return c.clone();
        }
    }

    warn!(
        "OpenCode Desktop config not found. Searched {:?}",
        candidates
    );

    candidates
        .first()
        .cloned()
        .unwrap_or_else(|| PathBuf::from("opencode/config.json"))
}
