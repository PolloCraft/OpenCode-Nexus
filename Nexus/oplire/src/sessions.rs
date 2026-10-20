use std::path::PathBuf;
use std::time::{SystemTime, UNIX_EPOCH};
use tokio::fs;
use tracing::{error, info, warn};

#[derive(serde::Serialize, serde::Deserialize, Clone, Debug, PartialEq)]
#[serde(rename_all = "snake_case")]
pub enum SessionStatus {
    Active,
    LimitReached,
    Paused,
    Resumable,
    Completed,
}

impl SessionStatus {
    pub fn as_str(&self) -> &'static str {
        match self {
            SessionStatus::Active => "active",
            SessionStatus::LimitReached => "limit_reached",
            SessionStatus::Paused => "paused",
            SessionStatus::Resumable => "resumable",
            SessionStatus::Completed => "completed",
        }
    }
}

#[derive(serde::Serialize, serde::Deserialize, Clone, Debug)]
pub struct TokenUsage {
    pub input_tokens: u64,
    pub output_tokens: u64,
    pub total_tokens: u64,
}

#[derive(serde::Serialize, serde::Deserialize, Clone, Debug)]
pub struct SessionInfo {
    pub id: String,
    pub path: String,
    pub folder: Option<String>,
    pub conversation_id: Option<String>,
    pub created_at: u64,
    pub last_modified: u64,
    pub size_bytes: u64,
    pub is_valid: bool,
    pub error_message: Option<String>,
    pub status: SessionStatus,
    pub token_usage: Option<TokenUsage>,
    pub limit_reached_at: Option<u64>,
    pub limit_reason: Option<String>,
    pub message_count: u32,
    pub resumable: bool,
    pub model: Option<String>,
}

#[derive(serde::Serialize, serde::Deserialize)]
struct SessionState {
    sessions: Vec<SessionInfo>,
    last_cleanup: u64,
    total_corrupted: u32,
    total_fixed: u32,
    total_limit_reached: u32,
    total_resumed: u32,
}

pub struct SessionGuard {
    sessions_dir: PathBuf,
    state_path: PathBuf,
}

impl SessionGuard {
    pub fn new() -> Self {
        let sessions_dir = Self::get_sessions_dir();
        let state_path = Self::get_state_path();
        Self {
            sessions_dir,
            state_path,
        }
    }

    fn get_sessions_dir() -> PathBuf {
        if cfg!(target_os = "windows") {
            std::env::var("LOCALAPPDATA")
                .map(PathBuf::from)
                .unwrap_or_else(|_| PathBuf::from("."))
                .join("oplire/sessions")
        } else if cfg!(target_os = "macos") {
            std::env::var("HOME")
                .map(PathBuf::from)
                .unwrap_or_else(|_| PathBuf::from("."))
                .join("Library/Application Support/oplire/sessions")
        } else {
            std::env::var("XDG_DATA_HOME")
                .map(PathBuf::from)
                .unwrap_or_else(|_| {
                    std::env::var("HOME")
                        .map(PathBuf::from)
                        .unwrap_or_else(|_| PathBuf::from("."))
                        .join(".local/share")
                })
                .join("oplire/sessions")
        }
    }

    fn get_state_path() -> PathBuf {
        Self::get_sessions_dir().join("guard_state.json")
    }

    pub fn get_sessions_dir_path(&self) -> &str {
        self.sessions_dir.to_str().unwrap_or("")
    }

    fn now_secs() -> u64 {
        SystemTime::now()
            .duration_since(UNIX_EPOCH)
            .map(|d| d.as_secs())
            .unwrap_or(0)
    }

    pub async fn init(&self) {
        if let Err(e) = fs::create_dir_all(&self.sessions_dir).await {
            error!("Failed to create sessions directory: {}", e);
        }
        info!("Session guard initialized at {}", self.sessions_dir.display());
    }

    pub async fn scan_opencode_sessions(&self) -> Vec<SessionInfo> {
        let mut sessions = Vec::new();
        let opencode_dirs = Self::get_opencode_session_dirs();

        for dir in &opencode_dirs {
            if !dir.exists() {
                continue;
            }

            if let Ok(mut entries) = fs::read_dir(dir).await {
                while let Ok(Some(entry)) = entries.next_entry().await {
                    let path = entry.path();
                    if path.extension().and_then(|e| e.to_str()) == Some("json") {
                        if let Some(info) = self.analyze_session_file(&path).await {
                            sessions.push(info);
                        }
                    }
                }
            }
        }

        let state = SessionState {
            sessions: sessions.clone(),
            last_cleanup: Self::now_secs(),
            total_corrupted: sessions.iter().filter(|s| !s.is_valid).count() as u32,
            total_fixed: 0,
            total_limit_reached: sessions
                .iter()
                .filter(|s| s.status == SessionStatus::LimitReached)
                .count() as u32,
            total_resumed: 0,
        };
        let _ = self.save_state(&state).await;

        sessions
    }

    fn get_opencode_session_dirs() -> Vec<PathBuf> {
        let mut dirs = Vec::new();

        if let Ok(appdata) = std::env::var("APPDATA") {
            dirs.push(PathBuf::from(&appdata).join("opencode/sessions"));
        }

        if let Ok(localappdata) = std::env::var("LOCALAPPDATA") {
            dirs.push(PathBuf::from(&localappdata).join("opencode/sessions"));
        }

        if let Ok(home) = std::env::var("USERPROFILE") {
            dirs.push(PathBuf::from(home).join(".opencode/sessions"));
        }

        if let Ok(home) = std::env::var("HOME") {
            dirs.push(PathBuf::from(&home).join(".opencode/sessions"));
            dirs.push(PathBuf::from(&home).join(".config/opencode/sessions"));
        }

        dirs
    }

    async fn analyze_session_file(&self, path: &PathBuf) -> Option<SessionInfo> {
        let metadata = fs::metadata(path).await.ok()?;
        let modified = metadata
            .modified()
            .ok()
            .and_then(|t| t.duration_since(UNIX_EPOCH).ok())
            .map(|d| d.as_secs())
            .unwrap_or(0);

        let content = fs::read_to_string(path).await.ok()?;

        let id = path
            .file_stem()
            .and_then(|s| s.to_str())
            .unwrap_or("unknown")
            .to_string();

        let folder = path
            .parent()
            .and_then(|p| p.file_name())
            .and_then(|f| f.to_str())
            .map(|s| s.to_string());

        let parsed: Option<serde_json::Value> = serde_json::from_str(&content).ok();

        let (is_valid, error_message) = self.validate_session_content(&content, &parsed);

        let (status, limit_reached_at, limit_reason, resumable, message_count, model, token_usage) =
            if let Some(ref json) = parsed {
                self.extract_session_metadata(json)
            } else {
                (SessionStatus::Active, None, None, false, 0, None, None)
            };

        let conversation_id = parsed.as_ref().and_then(|j| {
            j.get("conversation_id")
                .or_else(|| j.get("id"))
                .and_then(|v| v.as_str())
                .map(|s| s.to_string())
        });

        Some(SessionInfo {
            id,
            path: path.display().to_string(),
            folder,
            conversation_id,
            created_at: modified,
            last_modified: modified,
            size_bytes: metadata.len(),
            is_valid,
            error_message,
            status,
            token_usage,
            limit_reached_at,
            limit_reason,
            message_count,
            resumable,
            model,
        })
    }

    fn validate_session_content(
        &self,
        content: &str,
        parsed: &Option<serde_json::Value>,
    ) -> (bool, Option<String>) {
        if content.trim().is_empty() {
            return (false, Some("Session file is empty".to_string()));
        }

        let json = match parsed {
            Some(j) => j,
            None => return (false, Some("Session file contains invalid JSON".to_string())),
        };

        if let Some(obj) = json.as_object() {
            if obj.contains_key("corrupted") && obj["corrupted"].as_bool().unwrap_or(false) {
                return (false, Some("Session file is marked as corrupted".to_string()));
            }

            if obj.contains_key("error") && !obj["error"].is_null() {
                let error_msg = obj["error"]
                    .as_str()
                    .unwrap_or("Unknown error");
                let error_lower = error_msg.to_lowercase();

                if error_lower.contains("rate limit")
                    || error_lower.contains("token limit")
                    || error_lower.contains("quota")
                    || error_lower.contains("429")
                    || error_lower.contains("limit reached")
                    || error_lower.contains("too many requests")
                {
                    return (true, Some(format!("Token limit reached: {}", error_msg)));
                }

                return (false, Some(format!("Session error: {}", error_msg)));
            }

            if obj.contains_key("oplire_limit_reached") {
                return (true, Some("Token limit reached (oplire marker)".to_string()));
            }

            if obj.contains_key("messages") {
                if let Some(msgs) = obj["messages"].as_array() {
                    if msgs.is_empty() {
                        return (true, None);
                    }

                    for msg in msgs {
                        if !msg.is_object() {
                            return (false, Some("Invalid message structure".to_string()));
                        }
                        if msg.get("role").is_none() || msg.get("content").is_none() {
                            return (
                                false,
                                Some("Message missing role or content".to_string()),
                            );
                        }
                    }

                    return (true, None);
                }
            }

            return (true, None);
        }

        if json.is_array() {
            return (true, None);
        }

        (false, Some("Session has unexpected structure".to_string()))
    }

    fn extract_session_metadata(
        &self,
        json: &serde_json::Value,
    ) -> (
        SessionStatus,
        Option<u64>,
        Option<String>,
        bool,
        u32,
        Option<String>,
        Option<TokenUsage>,
    ) {
        let status = if let Some(s) = json.get("oplire_status").and_then(|v| v.as_str()) {
            match s {
                "active" => SessionStatus::Active,
                "limit_reached" => SessionStatus::LimitReached,
                "paused" => SessionStatus::Paused,
                "resumable" => SessionStatus::Resumable,
                "completed" => SessionStatus::Completed,
                _ => SessionStatus::Active,
            }
        } else if json.get("oplire_limit_reached").is_some() {
            SessionStatus::LimitReached
        } else {
            SessionStatus::Active
        };

        let limit_reached_at = json
            .get("oplire_limit_reached_at")
            .and_then(|v| v.as_u64());

        let limit_reason = json
            .get("oplire_limit_reason")
            .and_then(|v| v.as_str())
            .map(|s| s.to_string());

        let resumable = json
            .get("oplire_resumable")
            .and_then(|v| v.as_bool())
            .unwrap_or(status == SessionStatus::LimitReached);

        let message_count = json
            .get("messages")
            .and_then(|v| v.as_array())
            .map(|a| a.len() as u32)
            .unwrap_or(0);

        let model = json
            .get("model")
            .and_then(|v| v.as_str())
            .map(|s| s.to_string());

        let token_usage = json.get("oplire_token_usage").and_then(|usage| {
            Some(TokenUsage {
                input_tokens: usage.get("input_tokens").and_then(|v| v.as_u64()).unwrap_or(0),
                output_tokens: usage.get("output_tokens").and_then(|v| v.as_u64()).unwrap_or(0),
                total_tokens: usage.get("total_tokens").and_then(|v| v.as_u64()).unwrap_or(0),
            })
        });

        (status, limit_reached_at, limit_reason, resumable, message_count, model, token_usage)
    }

    pub async fn mark_session_limit_reached(
        &self,
        session_path: &str,
        reason: &str,
        token_usage: Option<TokenUsage>,
    ) -> Result<(), String> {
        let path = PathBuf::from(session_path);
        if !path.exists() {
            return Err(format!("Session file not found: {}", session_path));
        }

        let content = fs::read_to_string(&path)
            .await
            .map_err(|e| e.to_string())?;

        let mut json: serde_json::Value = serde_json::from_str(&content)
            .map_err(|e| format!("Invalid JSON: {}", e))?;

        let now = Self::now_secs();

        if let Some(obj) = json.as_object_mut() {
            obj.insert(
                "oplire_status".to_string(),
                serde_json::Value::String("limit_reached".to_string()),
            );
            obj.insert("oplire_limit_reached".to_string(), serde_json::json!(true));
            obj.insert("oplire_limit_reached_at".to_string(), serde_json::json!(now));
            obj.insert(
                "oplire_limit_reason".to_string(),
                serde_json::Value::String(reason.to_string()),
            );
            obj.insert("oplire_resumable".to_string(), serde_json::json!(true));

            if let Some(usage) = token_usage {
                obj.insert(
                    "oplire_token_usage".to_string(),
                    serde_json::json!({
                        "input_tokens": usage.input_tokens,
                        "output_tokens": usage.output_tokens,
                        "total_tokens": usage.total_tokens,
                    }),
                );
            }
        }

        let pretty = serde_json::to_string_pretty(&json).map_err(|e| e.to_string())?;
        fs::write(&path, pretty)
            .await
            .map_err(|e| format!("Failed to write session: {}", e))?;

        info!(
            "Session marked as limit_reached: {} (reason: {})",
            session_path, reason
        );
        Ok(())
    }

    pub async fn mark_session_resumable(&self, session_path: &str) -> Result<(), String> {
        let path = PathBuf::from(session_path);
        if !path.exists() {
            return Err(format!("Session file not found: {}", session_path));
        }

        let content = fs::read_to_string(&path)
            .await
            .map_err(|e| e.to_string())?;

        let mut json: serde_json::Value = serde_json::from_str(&content)
            .map_err(|e| format!("Invalid JSON: {}", e))?;

        if let Some(obj) = json.as_object_mut() {
            obj.insert(
                "oplire_status".to_string(),
                serde_json::Value::String("resumable".to_string()),
            );
            obj.insert("oplire_resumable".to_string(), serde_json::json!(true));
        }

        let pretty = serde_json::to_string_pretty(&json).map_err(|e| e.to_string())?;
        fs::write(&path, pretty)
            .await
            .map_err(|e| format!("Failed to write session: {}", e))?;

        info!("Session marked as resumable: {}", session_path);
        Ok(())
    }

    pub async fn mark_session_completed(&self, session_path: &str) -> Result<(), String> {
        let path = PathBuf::from(session_path);
        if !path.exists() {
            return Err(format!("Session file not found: {}", session_path));
        }

        let content = fs::read_to_string(&path)
            .await
            .map_err(|e| e.to_string())?;

        let mut json: serde_json::Value = serde_json::from_str(&content)
            .map_err(|e| format!("Invalid JSON: {}", e))?;

        if let Some(obj) = json.as_object_mut() {
            obj.insert(
                "oplire_status".to_string(),
                serde_json::Value::String("completed".to_string()),
            );
            obj.insert("oplire_resumable".to_string(), serde_json::json!(false));
        }

        let pretty = serde_json::to_string_pretty(&json).map_err(|e| e.to_string())?;
        fs::write(&path, pretty)
            .await
            .map_err(|e| format!("Failed to write session: {}", e))?;

        info!("Session marked as completed: {}", session_path);
        Ok(())
    }

    pub async fn fix_corrupted_sessions(&self) -> Result<u32, String> {
        let sessions = self.scan_opencode_sessions().await;
        let corrupted: Vec<&SessionInfo> = sessions
            .iter()
            .filter(|s| !s.is_valid && s.status != SessionStatus::LimitReached)
            .collect();

        if corrupted.is_empty() {
            info!("No corrupted sessions found (limit_reached sessions are preserved)");
            return Ok(0);
        }

        info!(
            "Found {} truly corrupted sessions (excluding {} limit_reached)",
            corrupted.len(),
            sessions
                .iter()
                .filter(|s| s.status == SessionStatus::LimitReached)
                .count()
        );

        let mut fixed = 0;

        for session in &corrupted {
            let path = PathBuf::from(&session.path);
            let backup_path = path.with_extension("json.corrupted");

            if let Err(e) = fs::copy(&path, &backup_path).await {
                warn!("Failed to backup corrupted session {}: {}", session.id, e);
                continue;
            }

            let fixed_content = serde_json::json!({
                "id": session.id,
                "messages": [{
                    "role": "assistant",
                    "content": "[Session was corrupted and has been reset]"
                }],
                "metadata": {
                    "oplire_fixed": true,
                    "fixed_at": Self::now_secs(),
                    "original_error": session.error_message.clone().unwrap_or_default()
                }
            });

            let pretty =
                serde_json::to_string_pretty(&fixed_content).map_err(|e| e.to_string())?;

            if let Err(e) = fs::write(&path, pretty).await {
                warn!("Failed to fix session {}: {}", session.id, e);
                continue;
            }

            info!("Fixed corrupted session: {}", session.id);
            fixed += 1;
        }

        let mut state = self.load_state().await.unwrap_or(SessionState {
            sessions: Vec::new(),
            last_cleanup: 0,
            total_corrupted: 0,
            total_fixed: 0,
            total_limit_reached: 0,
            total_resumed: 0,
        });
        state.total_fixed += fixed;
        let _ = self.save_state(&state).await;

        info!("Fixed {} corrupted sessions", fixed);
        Ok(fixed)
    }

    pub async fn cleanup_old_sessions(&self, max_age_hours: u64) -> Result<u32, String> {
        let sessions = self.scan_opencode_sessions().await;
        let now = Self::now_secs();
        let max_age_secs = max_age_hours * 3600;

        let mut removed = 0;

        for session in &sessions {
            let age = now.saturating_sub(session.last_modified);

            if age > max_age_secs && session.is_valid {
                if session.status == SessionStatus::LimitReached
                    || session.status == SessionStatus::Resumable
                {
                    info!(
                        "Skipping limit_reached/resumable session: {} (age: {}h)",
                        session.id,
                        age / 3600
                    );
                    continue;
                }

                let path = PathBuf::from(&session.path);
                let archive_path = path.with_extension("json.archived");

                if let Err(e) = fs::rename(&path, &archive_path).await {
                    warn!("Failed to archive session {}: {}", session.id, e);
                    continue;
                }

                info!(
                    "Archived old session: {} (age: {}h)",
                    session.id,
                    age / 3600
                );
                removed += 1;
            }
        }

        info!("Archived {} old sessions", removed);
        Ok(removed)
    }

    pub async fn get_resumable_sessions(&self) -> Vec<SessionInfo> {
        let sessions = self.scan_opencode_sessions().await;
        sessions
            .into_iter()
            .filter(|s| {
                s.status == SessionStatus::LimitReached
                    || s.status == SessionStatus::Resumable
                    || s.resumable
            })
            .collect()
    }

    pub async fn get_sessions_by_folder(&self) -> std::collections::HashMap<String, Vec<SessionInfo>> {
        let sessions = self.scan_opencode_sessions().await;
        let mut by_folder: std::collections::HashMap<String, Vec<SessionInfo>> =
            std::collections::HashMap::new();

        for session in sessions {
            let folder = session
                .folder
                .clone()
                .unwrap_or_else(|| "unknown".to_string());
            by_folder.entry(folder).or_default().push(session);
        }

        by_folder
    }

    pub async fn find_session_by_id(
        &self,
        session_id: &str,
    ) -> Option<SessionInfo> {
        let sessions = self.scan_opencode_sessions().await;
        sessions.into_iter().find(|s| s.id == session_id)
    }

    pub async fn get_health_report(&self) -> serde_json::Value {
        let sessions = self.scan_opencode_sessions().await;
        let total = sessions.len();
        let valid = sessions.iter().filter(|s| s.is_valid).count();
        let corrupted = total - valid;
        let limit_reached = sessions
            .iter()
            .filter(|s| s.status == SessionStatus::LimitReached)
            .count();
        let resumable = sessions
            .iter()
            .filter(|s| s.resumable || s.status == SessionStatus::Resumable)
            .count();
        let state = self.load_state().await;

        let by_folder = self.get_sessions_by_folder().await;
        let folder_summary: serde_json::Value = by_folder
            .iter()
            .map(|(name, sessions)| {
                serde_json::json!({
                    "name": name,
                    "count": sessions.len(),
                    "limit_reached": sessions.iter().filter(|s| s.status == SessionStatus::LimitReached).count(),
                    "active": sessions.iter().filter(|s| s.status == SessionStatus::Active).count(),
                })
            })
            .collect();

        serde_json::json!({
            "total_sessions": total,
            "valid_sessions": valid,
            "corrupted_sessions": corrupted,
            "limit_reached_sessions": limit_reached,
            "resumable_sessions": resumable,
            "health_score": if total > 0 { (valid as f64 / total as f64 * 100.0) as u32 } else { 100 },
            "total_fixed_all_time": state.as_ref().map(|s| s.total_fixed).unwrap_or(0),
            "total_limit_reached_all_time": state.as_ref().map(|s| s.total_limit_reached).unwrap_or(0),
            "total_resumed_all_time": state.as_ref().map(|s| s.total_resumed).unwrap_or(0),
            "last_cleanup": state.as_ref().map(|s| s.last_cleanup).unwrap_or(0),
            "folders": folder_summary,
            "corrupted_details": sessions.iter()
                .filter(|s| !s.is_valid)
                .map(|s| serde_json::json!({
                    "id": s.id,
                    "error": s.error_message,
                    "size": s.size_bytes,
                    "status": s.status.as_str()
                }))
                .collect::<Vec<_>>(),
            "limit_reached_details": sessions.iter()
                .filter(|s| s.status == SessionStatus::LimitReached)
                .map(|s| serde_json::json!({
                    "id": s.id,
                    "folder": s.folder,
                    "limit_reason": s.limit_reason,
                    "limit_reached_at": s.limit_reached_at,
                    "resumable": s.resumable,
                    "message_count": s.message_count,
                    "model": s.model
                }))
                .collect::<Vec<_>>()
        })
    }

    async fn save_state(&self, state: &SessionState) -> Result<(), String> {
        if let Some(parent) = self.state_path.parent() {
            fs::create_dir_all(parent)
                .await
                .map_err(|e| format!("Failed to create state dir: {}", e))?;
        }

        let json = serde_json::to_string_pretty(state).map_err(|e| e.to_string())?;
        fs::write(&self.state_path, json)
            .await
            .map_err(|e| format!("Failed to save state: {}", e))?;

        Ok(())
    }

    async fn load_state(&self) -> Option<SessionState> {
        let content = fs::read_to_string(&self.state_path).await.ok()?;
        serde_json::from_str(&content).ok()
    }
}
