use tracing::info;

/// Represents all OpenCode-related directories detected on the system.
#[derive(Debug, Clone, Default, serde::Serialize)]
pub struct OpenCodeFolders {
    pub root: Option<std::path::PathBuf>,
    pub config: Option<std::path::PathBuf>,
    pub cache: Option<std::path::PathBuf>,
    pub data: Option<std::path::PathBuf>,
    pub desktop_config: Option<std::path::PathBuf>,
    pub desktop_root: Option<std::path::PathBuf>,
}

impl OpenCodeFolders {
    /// Get the size of a directory in bytes.
    pub fn dir_size(path: &std::path::Path) -> u64 {
        if !path.exists() {
            return 0;
        }
        let mut total = 0;
        if let Ok(entries) = std::fs::read_dir(path) {
            for entry in entries.flatten() {
                let meta = entry.metadata().ok();
                if let Some(m) = meta {
                    if m.is_dir() {
                        total += Self::dir_size(&entry.path());
                    } else {
                        total += m.len();
                    }
                }
            }
        }
        total
    }

    /// Get a summary of all folder sizes.
    pub fn get_summary(&self) -> serde_json::Value {
        let cache_size = self.cache.as_ref().map(|p| Self::dir_size(p)).unwrap_or(0);
        let data_size = self.data.as_ref().map(|p| Self::dir_size(p)).unwrap_or(0);

        serde_json::json!({
            "root": self.root.as_ref().map(|p| p.display().to_string()),
            "config": self.config.as_ref().map(|p| p.display().to_string()),
            "config_exists": self.config.as_ref().map(|p| p.exists()).unwrap_or(false),
            "cache": self.cache.as_ref().map(|p| p.display().to_string()),
            "cache_exists": self.cache.as_ref().map(|p| p.exists()).unwrap_or(false),
            "cache_size_bytes": cache_size,
            "cache_size_human": Self::human_size(cache_size),
            "data": self.data.as_ref().map(|p| p.display().to_string()),
            "data_exists": self.data.as_ref().map(|p| p.exists()).unwrap_or(false),
            "data_size_bytes": data_size,
            "data_size_human": Self::human_size(data_size),
            "desktop_config": self.desktop_config.as_ref().map(|p| p.display().to_string()),
            "desktop_config_exists": self.desktop_config.as_ref().map(|p| p.exists()).unwrap_or(false),
        })
    }

    /// Clear the cache directory contents (does not remove the directory itself).
    pub fn clear_cache(&self) -> Result<serde_json::Value, String> {
        let cache_path = self.cache.as_ref().ok_or("Cache folder not detected")?;
        if !cache_path.exists() {
            return Ok(serde_json::json!({
                "success": true,
                "message": "Cache folder does not exist, nothing to clear.",
                "cleared_bytes": 0
            }));
        }

        let size_before = Self::dir_size(cache_path);
        let mut removed_count = 0u32;

        if let Ok(entries) = std::fs::read_dir(cache_path) {
            for entry in entries.flatten() {
                let path = entry.path();
                let result = if path.is_dir() {
                    std::fs::remove_dir_all(&path)
                } else {
                    std::fs::remove_file(&path)
                };
                if result.is_ok() {
                    removed_count += 1;
                }
            }
        }

        info!(
            "Cache cleared: {} items removed, {} bytes freed",
            removed_count, size_before
        );

        Ok(serde_json::json!({
            "success": true,
            "message": format!("Cache limpiado correctamente. {} archivos eliminados.", removed_count),
            "cleared_bytes": size_before,
            "cleared_human": Self::human_size(size_before),
            "items_removed": removed_count,
            "path": cache_path.display().to_string()
        }))
    }

    /// Clear all OpenCode data (cache + data directories).
    pub fn clear_all_data(&self) -> Result<serde_json::Value, String> {
        let mut results = Vec::new();
        let mut total_bytes = 0u64;

        if let Some(cache) = &self.cache {
            if cache.exists() {
                let size = Self::dir_size(cache);
                if let Err(e) = std::fs::remove_dir_all(cache) {
                    results.push(format!("Cache: error - {}", e));
                } else {
                    results.push(format!("Cache: {} limpiado", Self::human_size(size)));
                    total_bytes += size;
                }
            }
        }

        if let Some(data) = &self.data {
            if data.exists() {
                let size = Self::dir_size(data);
                if let Err(e) = std::fs::remove_dir_all(data) {
                    results.push(format!("Data: error - {}", e));
                } else {
                    results.push(format!("Data: {} limpiado", Self::human_size(size)));
                    total_bytes += size;
                }
            }
        }

        Ok(serde_json::json!({
            "success": true,
            "message": results.join("\n"),
            "cleared_bytes": total_bytes,
            "cleared_human": Self::human_size(total_bytes)
        }))
    }

    fn human_size(bytes: u64) -> String {
        if bytes < 1024 {
            format!("{} B", bytes)
        } else if bytes < 1024 * 1024 {
            format!("{:.1} KB", bytes as f64 / 1024.0)
        } else if bytes < 1024 * 1024 * 1024 {
            format!("{:.1} MB", bytes as f64 / (1024.0 * 1024.0))
        } else {
            format!("{:.2} GB", bytes as f64 / (1024.0 * 1024.0 * 1024.0))
        }
    }

    /// Detect all OpenCode-related folders (config, cache, data) for the current user.
    pub fn detect() -> Self {
        let mut folders = Self::default();

        if cfg!(target_os = "windows") {
            if let Ok(home) = std::env::var("USERPROFILE") {
                let home = std::path::PathBuf::from(home);
                folders.config = Some(home.join(".config").join("opencode"));
                folders.cache = Some(home.join(".cache").join("opencode"));
                folders.data = Some(home.join(".local").join("share").join("opencode"));
                folders.root = Some(home);
            }
        } else if cfg!(target_os = "macos") {
            if let Ok(home) = std::env::var("HOME") {
                let home = std::path::PathBuf::from(home);
                folders.config = Some(home.join("Library").join("Application Support").join("opencode"));
                folders.cache = Some(home.join("Library").join("Caches").join("opencode"));
                folders.data = Some(home.join("Library").join("Application Support").join("opencode"));
                folders.root = Some(home);
            }
        } else {
            if let Ok(home) = std::env::var("HOME") {
                let home = std::path::PathBuf::from(home);
                let xdg_cache = std::env::var("XDG_CACHE_HOME")
                    .map(std::path::PathBuf::from)
                    .unwrap_or_else(|_| home.join(".cache"));
                let xdg_config = std::env::var("XDG_CONFIG_HOME")
                    .map(std::path::PathBuf::from)
                    .unwrap_or_else(|_| home.join(".config"));
                let xdg_data = std::env::var("XDG_DATA_HOME")
                    .map(std::path::PathBuf::from)
                    .unwrap_or_else(|_| home.join(".local").join("share"));
                folders.config = Some(xdg_config.join("opencode"));
                folders.cache = Some(xdg_cache.join("opencode"));
                folders.data = Some(xdg_data.join("opencode"));
                folders.root = Some(home);
            }
        }

        // Also search for Desktop app config via bypass module paths
        let bypass = crate::bypass::DesktopBypass::new();
        if bypass.config_path.exists() {
            folders.desktop_config = Some(bypass.config_path.clone());
            folders.desktop_root = bypass.config_path.parent().map(|p| p.to_path_buf());
        }

        folders
    }
}

/// Proxy configuration for the Anthropic ↔ OpenCode Zen bridge.
#[derive(Debug, Clone)]
pub struct ProxyConfig {
    /// Address to listen on (default: 127.0.0.1:8080)
    pub listen_addr: String,
    /// OpenCode Zen API base URL (default: http://localhost:3000)
    pub opencode_base_url: String,
    /// API key for OpenCode Zen (if required)
    pub opencode_api_key: Option<String>,
    /// Maximum retry attempts after WARP reset
    pub max_retries: u32,
    /// Delay between WARP reset steps (milliseconds)
    pub warp_reset_delay_ms: u64,
}

/// A free model available on OpenCode Zen.
#[derive(Debug, Clone, serde::Serialize)]
pub struct FreeModel {
    /// Model identifier used by OpenCode Zen
    pub id: String,
    /// Display name shown in Claude Code
    pub display_name: String,
}

impl Default for ProxyConfig {
    fn default() -> Self {
        Self {
            listen_addr: "127.0.0.1:8080".to_string(),
            opencode_base_url: "http://localhost:3000".to_string(),
            opencode_api_key: None,
            max_retries: 3,
            warp_reset_delay_ms: 5000,
        }
    }
}

impl ProxyConfig {
    /// Returns the list of free models mapped to Anthropic schema.
    pub fn free_models() -> Vec<FreeModel> {
        vec![
            FreeModel {
                id: "nvidia/nemotron-3.5-lightning-30b-a3b".to_string(),
                display_name: "Nemotron 3.5 Lightning".to_string(),
            },
            FreeModel {
                id: "nemotron-3-ultra-free".to_string(),
                display_name: "Nemotron 3 Ultra".to_string(),
            },
            FreeModel {
                id: "inclusionai/ling-3.0-flash-fin".to_string(),
                display_name: "Ling 3.0 Flash Fin".to_string(),
            },
            FreeModel {
                id: "tencent/hy3-free".to_string(),
                display_name: "Hy3".to_string(),
            },
            FreeModel {
                id: "muse-spark-1.2-contributor-free".to_string(),
                display_name: "Muse Spark 1.2".to_string(),
            },
            FreeModel {
                id: "mimo-v2.5-free".to_string(),
                display_name: "MiMo V2.5".to_string(),
            },
            FreeModel {
                id: "big-pickle".to_string(),
                display_name: "Big Pickle".to_string(),
            },
        ]
    }

    /// Build Anthropic-compatible models response JSON.
    pub fn models_response() -> serde_json::Value {
        let models: Vec<serde_json::Value> = Self::free_models()
            .iter()
            .map(|m| {
                serde_json::json!({
                    "id": m.id,
                    "object": "model",
                    "created": 0,
                    "owned_by": "opencode-zen"
                })
            })
            .collect();

        serde_json::json!({
            "object": "list",
            "data": models
        })
    }
}

#[derive(Debug, Clone, serde::Serialize, serde::Deserialize)]
pub struct AppConfig {
    pub listen: String,
    pub upstream: String,
    pub max_retries: u32,
    pub warp_delay: u64,
}

impl Default for AppConfig {
    fn default() -> Self {
        Self {
            listen: "127.0.0.1:8080".to_string(),
            upstream: "http://localhost:3000".to_string(),
            max_retries: 3,
            warp_delay: 5000,
        }
    }
}

/// Get the platform-specific config directory
pub fn get_config_dir() -> std::path::PathBuf {
    if cfg!(target_os = "windows") {
        if let Ok(appdata) = std::env::var("APPDATA") {
            let mut p = std::path::PathBuf::from(appdata);
            p.push("oplire");
            return p;
        }
    } else if cfg!(target_os = "macos") {
        if let Ok(home) = std::env::var("HOME") {
            let mut p = std::path::PathBuf::from(home);
            p.push("Library");
            p.push("Application Support");
            p.push("oplire");
            return p;
        }
    }

    // Linux/Unix fallback
    if let Ok(xdg) = std::env::var("XDG_CONFIG_HOME") {
        let mut p = std::path::PathBuf::from(xdg);
        p.push("oplire");
        return p;
    }
    if let Ok(home) = std::env::var("HOME") {
        let mut p = std::path::PathBuf::from(home);
        p.push(".config");
        p.push("oplire");
        return p;
    }

    std::path::PathBuf::from("oplire")
}

/// Get the platform-specific data directory
pub fn get_data_dir() -> std::path::PathBuf {
    if cfg!(target_os = "windows") {
        if let Ok(localappdata) = std::env::var("LOCALAPPDATA") {
            let mut p = std::path::PathBuf::from(localappdata);
            p.push("oplire");
            return p;
        }
    } else if cfg!(target_os = "macos") {
        if let Ok(home) = std::env::var("HOME") {
            let mut p = std::path::PathBuf::from(home);
            p.push("Library");
            p.push("Application Support");
            p.push("oplire");
            return p;
        }
    }

    // Linux/Unix fallback
    if let Ok(xdg) = std::env::var("XDG_DATA_HOME") {
        let mut p = std::path::PathBuf::from(xdg);
        p.push("oplire");
        return p;
    }
    if let Ok(home) = std::env::var("HOME") {
        let mut p = std::path::PathBuf::from(home);
        p.push(".local");
        p.push("share");
        p.push("oplire");
        return p;
    }

    std::path::PathBuf::from("oplire")
}
