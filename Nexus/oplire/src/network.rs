use std::path::PathBuf;
use std::time::{SystemTime, UNIX_EPOCH};
use tokio::fs;
use tokio::process::Command;
use tracing::{error, info, warn};

#[derive(serde::Serialize, serde::Deserialize, Clone, Debug, PartialEq)]
pub enum IpMode {
    Dhcp,
    Static,
    Unknown,
}

#[derive(serde::Serialize, serde::Deserialize, Clone, Debug)]
pub enum AdapterStatus {
    Connected,
    Disconnected,
    Unknown,
}

#[derive(serde::Serialize, serde::Deserialize, Clone, Debug)]
pub struct AdapterInfo {
    pub name: String,
    pub friendly_name: String,
    pub status: AdapterStatus,
    pub ip_mode: IpMode,
    pub ipv4_address: Option<String>,
    pub ipv4_mask: Option<String>,
    pub ipv4_gateway: Option<String>,
    pub ipv4_dns: Vec<String>,
    pub ipv6_address: Option<String>,
    pub mac_address: Option<String>,
    pub is_wireless: bool,
    pub dhcp_server: Option<String>,
    pub lease_obtained: Option<String>,
    pub lease_expires: Option<String>,
}

#[derive(serde::Serialize, serde::Deserialize, Clone, Debug)]
pub struct ProxyConfig {
    pub enabled: bool,
    pub server: Option<String>,
    pub port: Option<String>,
    pub bypass: Option<String>,
}

#[derive(serde::Serialize, serde::Deserialize, Clone, Debug)]
pub struct NetworkSnapshot {
    pub timestamp: u64,
    pub source: String,
    pub adapters: Vec<AdapterInfo>,
    pub proxy: ProxyConfig,
    pub public_ip: Option<String>,
    pub hostname: Option<String>,
    pub warp_active: bool,
    pub notes: Option<String>,
}

#[derive(serde::Serialize, serde::Deserialize, Clone, Debug)]
pub struct RestorationResult {
    pub success: bool,
    pub status: String,
    pub restored_items: Vec<String>,
    pub failed_items: Vec<String>,
    pub warnings: Vec<String>,
    pub current_ip: Option<String>,
    pub original_ip: Option<String>,
    pub verification_passed: bool,
    pub message: String,
}

pub struct NetworkManager {
    state_dir: PathBuf,
    backup_path: PathBuf,
    history_path: PathBuf,
    log_path: PathBuf,
}

impl NetworkManager {
    pub fn new() -> Self {
        let state_dir = Self::get_state_dir();
        let backup_path = state_dir.join("network_backup.json");
        let history_path = state_dir.join("network_history.json");
        let log_path = state_dir.join("network_restore.log");
        Self {
            state_dir,
            backup_path,
            history_path,
            log_path,
        }
    }

    fn get_state_dir() -> PathBuf {
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

    fn now_secs() -> u64 {
        SystemTime::now()
            .duration_since(UNIX_EPOCH)
            .map(|d| d.as_secs())
            .unwrap_or(0)
    }

    pub async fn init(&self) {
        if let Err(e) = fs::create_dir_all(&self.state_dir).await {
            error!("Failed to create network state directory: {}", e);
        }
    }

    pub async fn capture_snapshot(&self, source: &str) -> Result<NetworkSnapshot, String> {
        info!("[NETWORK] Capturing network snapshot (source: {})", source);

        let adapters = self.detect_adapters().await;
        let proxy = self.detect_proxy().await;
        let public_ip = self.get_public_ip().await.ok();
        let hostname = self.get_hostname().await.ok();
        let warp_active = self.is_warp_active().await;

        let snapshot = NetworkSnapshot {
            timestamp: Self::now_secs(),
            source: source.to_string(),
            adapters,
            proxy,
            public_ip,
            hostname,
            warp_active,
            notes: None,
        };

        self.save_backup(&snapshot).await?;
        self.append_history(&snapshot).await;

        info!(
            "[NETWORK] Snapshot captured: {} adapters, public_ip={:?}",
            snapshot.adapters.len(),
            snapshot.public_ip
        );

        Ok(snapshot)
    }

    pub async fn get_current_state(&self) -> Result<NetworkSnapshot, String> {
        let adapters = self.detect_adapters().await;
        let proxy = self.detect_proxy().await;
        let public_ip = self.get_public_ip().await.ok();
        let hostname = self.get_hostname().await.ok();
        let warp_active = self.is_warp_active().await;

        Ok(NetworkSnapshot {
            timestamp: Self::now_secs(),
            source: "current".to_string(),
            adapters,
            proxy,
            public_ip,
            hostname,
            warp_active,
            notes: None,
        })
    }

    async fn detect_adapters(&self) -> Vec<AdapterInfo> {
        if cfg!(target_os = "windows") {
            self.detect_adapters_windows().await
        } else if cfg!(target_os = "macos") {
            self.detect_adapters_macos().await
        } else {
            self.detect_adapters_linux().await
        }
    }

    async fn detect_adapters_windows(&self) -> Vec<AdapterInfo> {
        let mut adapters = Vec::new();

        let output = Command::new("powershell")
            .args([
                "-NoProfile",
                "-Command",
                "Get-NetAdapter | Select-Object Name,InterfaceDescription,Status,MacAddress,LinkSpeed | ConvertTo-Json -Depth 2",
            ])
            .output()
            .await;

        if let Ok(out) = output {
            if out.status.success() {
                let json_str = String::from_utf8_lossy(&out.stdout);
                if let Ok(json) = serde_json::from_str::<serde_json::Value>(&json_str) {
                    let items = if json.is_array() {
                        json.as_array().cloned().unwrap_or_default()
                    } else {
                        vec![json]
                    };

                    for item in &items {
                        let name = item["Name"].as_str().unwrap_or("Unknown").to_string();
                        let friendly = item["InterfaceDescription"]
                            .as_str()
                            .unwrap_or(&name)
                            .to_string();
                        let status_str = item["Status"].as_str().unwrap_or("Unknown");
                        let mac = item["MacAddress"].as_str().map(|s| s.to_string());

                        let status = match status_str.to_lowercase().as_str() {
                            "up" => AdapterStatus::Connected,
                            "down" => AdapterStatus::Disconnected,
                            _ => AdapterStatus::Unknown,
                        };

                        let is_wireless = friendly.to_lowercase().contains("wireless")
                            || friendly.to_lowercase().contains("wifi")
                            || friendly.to_lowercase().contains("802.11")
                            || name.to_lowercase().contains("wi-fi");

                        let ip_info = self.get_adapter_ip_windows(&name).await;

                        adapters.push(AdapterInfo {
                            name: name.clone(),
                            friendly_name: friendly,
                            status,
                            ip_mode: ip_info.0,
                            ipv4_address: ip_info.1,
                            ipv4_mask: ip_info.2,
                            ipv4_gateway: ip_info.3,
                            ipv4_dns: ip_info.4,
                            ipv6_address: ip_info.5,
                            mac_address: mac,
                            is_wireless,
                            dhcp_server: None,
                            lease_obtained: None,
                            lease_expires: None,
                        });
                    }
                }
            }
        }

        adapters
    }

    async fn get_adapter_ip_windows(
        &self,
        adapter_name: &str,
    ) -> (IpMode, Option<String>, Option<String>, Option<String>, Vec<String>, Option<String>) {
        let mut ip_mode = IpMode::Unknown;
        let mut ipv4 = None;
        let mut mask = None;
        let mut gateway = None;
        let mut dns = Vec::new();
        let mut ipv6 = None;

        let cmd = format!(
            "Get-NetIPConfiguration -InterfaceAlias '{}' | ConvertTo-Json -Depth 4",
            adapter_name
        );

        if let Ok(out) = Command::new("powershell")
            .args(["-NoProfile", "-Command", &cmd])
            .output()
            .await
        {
            if out.status.success() {
                let json_str = String::from_utf8_lossy(&out.stdout);
                if let Ok(json) = serde_json::from_str::<serde_json::Value>(&json_str) {
                    if let Some(net) = json.get("NetIPv4Protocol") {
                        let dhcp = net["AddressOrigin"].as_str().unwrap_or("Unknown");
                        ip_mode = match dhcp.to_lowercase().as_str() {
                            "dhcp" => IpMode::Dhcp,
                            "static" => IpMode::Static,
                            _ => IpMode::Unknown,
                        };
                    }

                    if let Some(ip) = json.get("IPv4Address") {
                        if let Some(addr) = ip.get("IPAddress").and_then(|v| v.as_str()) {
                            ipv4 = Some(addr.to_string());
                        }
                        if let Some(p) = ip.get("PrefixLength").and_then(|v| v.as_u64()) {
                            mask = Some(Self::prefix_to_mask(p as u32));
                        }
                    }

                    if let Some(gw) = json.get("IPv4DefaultGateway") {
                        if let Some(addr) = gw.get("IPAddress").and_then(|v| v.as_str()) {
                            gateway = Some(addr.to_string());
                        }
                    }

                    if let Some(d) = json.get("DNSServer") {
                        if let Some(arr) = d.as_array() {
                            for server in arr {
                                if let Some(addr) = server.get("IPAddress").and_then(|v| v.as_str())
                                {
                                    dns.push(addr.to_string());
                                }
                            }
                        } else if let Some(addr) = d.get("IPAddress").and_then(|v| v.as_str()) {
                            dns.push(addr.to_string());
                        }
                    }

                    if let Some(ip6) = json.get("IPv6Address") {
                        if let Some(addr) = ip6.get("IPAddress").and_then(|v| v.as_str()) {
                            ipv6 = Some(addr.to_string());
                        }
                    }
                }
            }
        }

        (ip_mode, ipv4, mask, gateway, dns, ipv6)
    }

    fn prefix_to_mask(prefix: u32) -> String {
        let mask = if prefix == 0 {
            0u32
        } else {
            !0u32 << (32 - prefix)
        };
        format!(
            "{}.{}.{}.{}",
            (mask >> 24) & 0xFF,
            (mask >> 16) & 0xFF,
            (mask >> 8) & 0xFF,
            mask & 0xFF
        )
    }

    async fn detect_adapters_linux(&self) -> Vec<AdapterInfo> {
        let mut adapters = Vec::new();

        if let Ok(out) = Command::new("ip")
            .args(["-o", "link", "show"])
            .output()
            .await
        {
            if out.status.success() {
                let output = String::from_utf8_lossy(&out.stdout);
                for line in output.lines() {
                    if let Some(name) = line.split(':').nth(1) {
                        let name = name.trim().to_string();
                        if name == "lo" || name.starts_with("docker") || name.starts_with("br-")
                        {
                            continue;
                        }

                        let status = if line.contains("state UP") {
                            AdapterStatus::Connected
                        } else if line.contains("state DOWN") {
                            AdapterStatus::Disconnected
                        } else {
                            AdapterStatus::Unknown
                        };

                        let ip_info = self.get_adapter_ip_linux(&name).await;
                        let is_wireless = name.starts_with("wlan") || name.starts_with("wlp");

                        adapters.push(AdapterInfo {
                            name: name.clone(),
                            friendly_name: name,
                            status,
                            ip_mode: ip_info.0,
                            ipv4_address: ip_info.1,
                            ipv4_mask: None,
                            ipv4_gateway: ip_info.2,
                            ipv4_dns: ip_info.3,
                            ipv6_address: ip_info.4,
                            mac_address: None,
                            is_wireless,
                            dhcp_server: None,
                            lease_obtained: None,
                            lease_expires: None,
                        });
                    }
                }
            }
        }

        adapters
    }

    async fn get_adapter_ip_linux(
        &self,
        interface: &str,
    ) -> (IpMode, Option<String>, Option<String>, Vec<String>, Option<String>) {
        let mut ip_mode = IpMode::Unknown;
        let mut ipv4 = None;
        let mut gateway = None;
        let mut dns = Vec::new();
        let mut ipv6 = None;

        if let Ok(out) = Command::new("ip")
            .args(["addr", "show", interface])
            .output()
            .await
        {
            if out.status.success() {
                let output = String::from_utf8_lossy(&out.stdout);
                for line in output.lines() {
                    if line.contains("inet ") && !line.contains("inet6") {
                        if let Some(addr) = line.split_whitespace().nth(1) {
                            ipv4 = Some(addr.split('/').next().unwrap_or(addr).to_string());
                        }
                    }
                    if line.contains("inet6 ") {
                        if let Some(addr) = line.split_whitespace().nth(1) {
                            ipv6 = Some(addr.split('/').next().unwrap_or(addr).to_string());
                        }
                    }
                }
            }
        }

        if let Ok(out) = Command::new("ip")
            .args(["route", "show", "dev", interface])
            .output()
            .await
        {
            if out.status.success() {
                let output = String::from_utf8_lossy(&out.stdout);
                for line in output.lines() {
                    if line.contains("default") {
                        if let Some(gw) = line.split_whitespace().nth(2) {
                            gateway = Some(gw.to_string());
                        }
                    }
                }
            }
        }

        if let Ok(out) = Command::new("resolvectl")
            .args(["status", interface])
            .output()
            .await
        {
            if out.status.success() {
                let output = String::from_utf8_lossy(&out.stdout);
                for line in output.lines() {
                    if line.contains("DNS Servers:") || line.contains("DNS Server:") {
                        if let Some(server) = line.split(':').nth(1) {
                            dns.push(server.trim().to_string());
                        }
                    }
                }
            }
        }

        if let Ok(content) = fs::read_to_string("/etc/dhcp/dhclient.conf").await {
            if content.contains("interface") && content.contains(interface) {
                ip_mode = IpMode::Dhcp;
            }
        }

        if let Ok(out) = Command::new("nmcli")
            .args(["-t", "-f", "IP4.method", "connection", "show", interface])
            .output()
            .await
        {
            if out.status.success() {
                let output = String::from_utf8_lossy(&out.stdout).trim().to_string();
                if output.contains("auto") {
                    ip_mode = IpMode::Dhcp;
                } else if output.contains("manual") {
                    ip_mode = IpMode::Static;
                }
            }
        }

        (ip_mode, ipv4, gateway, dns, ipv6)
    }

    async fn detect_adapters_macos(&self) -> Vec<AdapterInfo> {
        let mut adapters = Vec::new();

        if let Ok(out) = Command::new("networksetup")
            .args(["-listallhardwareports"])
            .output()
            .await
        {
            if out.status.success() {
                let output = String::from_utf8_lossy(&out.stdout);
                let mut current_name = String::new();
                let mut current_device = String::new();

                for line in output.lines() {
                    if line.starts_with("Hardware Port:") {
                        current_name = line.replace("Hardware Port:", "").trim().to_string();
                    } else if line.starts_with("Device:") {
                        current_device = line.replace("Device:", "").trim().to_string();
                    }

                    if !current_name.is_empty() && !current_device.is_empty() {
                        if current_device == "en0"
                            || current_device == "en1"
                            || current_device.starts_with("utun")
                        {
                            let ip_info = self.get_adapter_ip_macos(&current_device).await;
                            let status = if ip_info.1.is_some() {
                                AdapterStatus::Connected
                            } else {
                                AdapterStatus::Disconnected
                            };
                            let is_wireless = current_name.to_lowercase().contains("wi-fi")
                                || current_name.to_lowercase().contains("airport");

                            adapters.push(AdapterInfo {
                                name: current_device.clone(),
                                friendly_name: current_name.clone(),
                                status,
                                ip_mode: ip_info.0,
                                ipv4_address: ip_info.1,
                                ipv4_mask: None,
                                ipv4_gateway: ip_info.2,
                                ipv4_dns: ip_info.3,
                                ipv6_address: ip_info.4,
                                mac_address: None,
                                is_wireless,
                                dhcp_server: None,
                                lease_obtained: None,
                                lease_expires: None,
                            });
                        }
                        current_name.clear();
                        current_device.clear();
                    }
                }
            }
        }

        adapters
    }

    async fn get_adapter_ip_macos(
        &self,
        interface: &str,
    ) -> (IpMode, Option<String>, Option<String>, Vec<String>, Option<String>) {
        let mut ip_mode = IpMode::Unknown;
        let mut ipv4 = None;
        let mut gateway = None;
        let mut dns = Vec::new();
        let ipv6 = None;

        if let Ok(out) = Command::new("ipconfig")
            .args(["getifaddr", interface])
            .output()
            .await
        {
            if out.status.success() {
                let addr = String::from_utf8_lossy(&out.stdout).trim().to_string();
                if !addr.is_empty() {
                    ipv4 = Some(addr);
                }
            }
        }

        if let Ok(out) = Command::new("route")
            .args(["-n", "get", "default"])
            .output()
            .await
        {
            if out.status.success() {
                let output = String::from_utf8_lossy(&out.stdout);
                for line in output.lines() {
                    if line.contains("gateway:") {
                        gateway = Some(line.split(':').nth(1).unwrap_or("").trim().to_string());
                    }
                }
            }
        }

        if let Ok(out) = Command::new("scutil")
            .args(["--dns"])
            .output()
            .await
        {
            if out.status.success() {
                let output = String::from_utf8_lossy(&out.stdout);
                for line in output.lines() {
                    if line.trim().starts_with("nameserver[") {
                        if let Some(addr) = line.split(':').nth(1) {
                            let addr = addr.trim().to_string();
                            if !addr.is_empty() && !dns.contains(&addr) {
                                dns.push(addr);
                            }
                        }
                    }
                }
            }
        }

        if let Ok(out) = Command::new("ipconfig")
            .args(["getifaddr", interface])
            .output()
            .await
        {
            if !out.status.success() {
                ip_mode = IpMode::Dhcp;
            }
        }

        (ip_mode, ipv4, gateway, dns, ipv6)
    }

    async fn detect_proxy(&self) -> ProxyConfig {
        if cfg!(target_os = "windows") {
            self.detect_proxy_windows().await
        } else if cfg!(target_os = "macos") {
            self.detect_proxy_macos().await
        } else {
            self.detect_proxy_linux().await
        }
    }

    async fn detect_proxy_windows(&self) -> ProxyConfig {
        let mut proxy = ProxyConfig {
            enabled: false,
            server: None,
            port: None,
            bypass: None,
        };

        if let Ok(out) = Command::new("reg")
            .args([
                "query",
                "HKCU\\Software\\Microsoft\\Windows\\CurrentVersion\\Internet Settings",
                "/v",
                "ProxyEnable",
            ])
            .output()
            .await
        {
            if out.status.success() {
                let output = String::from_utf8_lossy(&out.stdout);
                proxy.enabled = output.contains("0x1");
            }
        }

        if let Ok(out) = Command::new("reg")
            .args([
                "query",
                "HKCU\\Software\\Microsoft\\Windows\\CurrentVersion\\Internet Settings",
                "/v",
                "ProxyServer",
            ])
            .output()
            .await
        {
            if out.status.success() {
                let output = String::from_utf8_lossy(&out.stdout);
                for line in output.lines() {
                    if line.contains("ProxyServer") {
                        if let Some(value) = line.split("REG_SZ").nth(1) {
                            let value = value.trim();
                            if let Some((server, port)) = value.rsplit_once(':') {
                                proxy.server = Some(server.to_string());
                                proxy.port = Some(port.to_string());
                            } else {
                                proxy.server = Some(value.to_string());
                            }
                        }
                    }
                }
            }
        }

        if let Ok(out) = Command::new("reg")
            .args([
                "query",
                "HKCU\\Software\\Microsoft\\Windows\\CurrentVersion\\Internet Settings",
                "/v",
                "ProxyOverride",
            ])
            .output()
            .await
        {
            if out.status.success() {
                let output = String::from_utf8_lossy(&out.stdout);
                for line in output.lines() {
                    if line.contains("ProxyOverride") {
                        if let Some(value) = line.split("REG_SZ").nth(1) {
                            proxy.bypass = Some(value.trim().to_string());
                        }
                    }
                }
            }
        }

        proxy
    }

    async fn detect_proxy_linux(&self) -> ProxyConfig {
        let mut proxy = ProxyConfig {
            enabled: false,
            server: None,
            port: None,
            bypass: None,
        };

        if let Ok(env_http) = std::env::var("http_proxy") {
            if !env_http.is_empty() {
                proxy.enabled = true;
                if let Some((server, port)) = env_http.rsplit_once(':') {
                    let server = server.trim_start_matches("http://").trim_start_matches("https://");
                    proxy.server = Some(server.to_string());
                    proxy.port = Some(port.to_string());
                }
            }
        }

        if let Ok(env_no) = std::env::var("no_proxy") {
            proxy.bypass = Some(env_no);
        }

        proxy
    }

    async fn detect_proxy_macos(&self) -> ProxyConfig {
        let mut proxy = ProxyConfig {
            enabled: false,
            server: None,
            port: None,
            bypass: None,
        };

        if let Ok(out) = Command::new("networksetup")
            .args(["-getwebproxy", "Wi-Fi"])
            .output()
            .await
        {
            if out.status.success() {
                let output = String::from_utf8_lossy(&out.stdout);
                for line in output.lines() {
                    if line.contains("Enabled:") {
                        proxy.enabled = line.contains("Yes");
                    }
                    if line.contains("Server:") {
                        proxy.server = Some(
                            line.split(':').nth(1).unwrap_or("").trim().to_string(),
                        );
                    }
                    if line.contains("Port:") {
                        proxy.port = Some(
                            line.split(':').nth(1).unwrap_or("").trim().to_string(),
                        );
                    }
                }
            }
        }

        proxy
    }

    async fn get_public_ip(&self) -> Result<String, String> {
        let client = reqwest::Client::builder()
            .timeout(std::time::Duration::from_secs(10))
            .build()
            .map_err(|e| e.to_string())?;

        let services = ["https://api.ipify.org?format=json", "https://httpbin.org/ip"];

        for url in &services {
            if let Ok(resp) = client.get(*url).send().await {
                if resp.status().is_success() {
                    if let Ok(json) = resp.json::<serde_json::Value>().await {
                        if let Some(ip) = json.get("ip").and_then(|v| v.as_str()) {
                            return Ok(ip.to_string());
                        }
                        if let Some(origin) = json.get("origin").and_then(|v| v.as_str()) {
                            return Ok(origin.to_string());
                        }
                    }
                }
            }
        }

        Err("Could not determine public IP".to_string())
    }

    async fn get_hostname(&self) -> Result<String, String> {
        let output = Command::new("hostname")
            .output()
            .await
            .map_err(|e| e.to_string())?;
        Ok(String::from_utf8_lossy(&output.stdout).trim().to_string())
    }

    async fn is_warp_active(&self) -> bool {
        if let Ok(out) = Command::new("warp-cli")
            .arg("status")
            .output()
            .await
        {
            if out.status.success() {
                let output = String::from_utf8_lossy(&out.stdout);
                return output.contains("Connected") || output.contains("Connected");
            }
        }
        false
    }

    pub async fn save_backup(&self, snapshot: &NetworkSnapshot) -> Result<(), String> {
        let json =
            serde_json::to_string_pretty(snapshot).map_err(|e| format!("Failed to serialize: {}", e))?;

        if let Some(parent) = self.backup_path.parent() {
            fs::create_dir_all(parent)
                .await
                .map_err(|e| format!("Failed to create dir: {}", e))?;
        }

        fs::write(&self.backup_path, json)
            .await
            .map_err(|e| format!("Failed to write backup: {}", e))?;

        info!("[NETWORK] Backup saved to {}", self.backup_path.display());
        Ok(())
    }

    pub async fn load_backup(&self) -> Option<NetworkSnapshot> {
        let content = fs::read_to_string(&self.backup_path).await.ok()?;
        serde_json::from_str(&content).ok()
    }

    pub async fn backup_exists(&self) -> bool {
        self.backup_path.exists()
    }

    async fn append_history(&self, snapshot: &NetworkSnapshot) {
        let mut history: Vec<NetworkSnapshot> =
            fs::read_to_string(&self.history_path)
                .await
                .ok()
                .and_then(|c| serde_json::from_str(&c).ok())
                .unwrap_or_default();

        history.push(snapshot.clone());

        if history.len() > 50 {
            history = history.split_off(history.len() - 50);
        }

        if let Ok(json) = serde_json::to_string_pretty(&history) {
            let _ = fs::write(&self.history_path, json).await;
        }
    }

    async fn write_log(&self, entry: &str) {
        let timestamp = Self::now_secs();
        let log_entry = format!("[{}] {}\n", timestamp, entry);
        if let Ok(mut file) = fs::OpenOptions::new()
            .create(true)
            .append(true)
            .open(&self.log_path)
            .await
        {
            use tokio::io::AsyncWriteExt;
            let _ = file.write_all(log_entry.as_bytes()).await;
        }
    }

    pub async fn restore_network(&self) -> Result<RestorationResult, String> {
        let backup = self
            .load_backup()
            .await
            .ok_or("No backup found. Cannot restore.".to_string())?;

        self.write_log(&format!(
            "Starting restoration from backup (timestamp: {})",
            backup.timestamp
        ))
        .await;

        let current = self.get_current_state().await?;

        self.write_log(&format!(
            "Current state: {} adapters, public_ip={:?}",
            current.adapters.len(),
            current.public_ip
        ))
        .await;

        let mut restored_items = Vec::new();
        let mut failed_items = Vec::new();
        let mut warnings = Vec::new();

        for backup_adapter in &backup.adapters {
            if let Some(current_adapter) = current
                .adapters
                .iter()
                .find(|a| a.name == backup_adapter.name || a.friendly_name == backup_adapter.friendly_name)
            {
                if current_adapter.ip_mode == backup_adapter.ip_mode
                    && current_adapter.ipv4_address == backup_adapter.ipv4_address
                    && current_adapter.ipv4_gateway == backup_adapter.ipv4_gateway
                {
                    self.write_log(&format!(
                        "Adapter {} already matches backup, skipping",
                        backup_adapter.name
                    ))
                    .await;
                    continue;
                }

                self.write_log(&format!(
                    "Restoring adapter {} (from {:?} to {:?})",
                    backup_adapter.name, current_adapter.ip_mode, backup_adapter.ip_mode
                ))
                .await;

                match self.restore_adapter(backup_adapter).await {
                    Ok(msg) => {
                        restored_items.push(format!("{}: {}", backup_adapter.name, msg));
                        self.write_log(&format!("Restored {}: {}", backup_adapter.name, msg))
                            .await;
                    }
                    Err(e) => {
                        failed_items.push(format!("{}: {}", backup_adapter.name, e.clone()));
                        self.write_log(&format!("Failed to restore {}: {}", backup_adapter.name, e))
                            .await;
                    }
                }
            } else {
                warnings.push(format!(
                    "Adapter {} not found in current state",
                    backup_adapter.name
                ));
                self.write_log(&format!(
                    "Warning: Adapter {} from backup not found in current state",
                    backup_adapter.name
                ))
                .await;
            }
        }

        if backup.proxy.enabled != current.proxy.enabled
            || backup.proxy.server != current.proxy.server
        {
            self.write_log("Restoring proxy settings").await;
            match self.restore_proxy(&backup.proxy).await {
                Ok(msg) => {
                    restored_items.push(format!("Proxy: {}", msg));
                    self.write_log(&format!("Proxy restored: {}", msg)).await;
                }
                Err(e) => {
                    failed_items.push(format!("Proxy: {}", e.clone()));
                    self.write_log(&format!("Proxy restore failed: {}", e)).await;
                }
            }
        }

        let final_state = self.get_current_state().await?;
        let verification_passed = self.verify_restoration(&backup, &final_state);

        let current_ip = final_state
            .adapters
            .iter()
            .find(|a| a.ipv4_address.is_some())
            .and_then(|a| a.ipv4_address.clone());

        let success = failed_items.is_empty() && verification_passed;
        let status = if success {
            "completed".to_string()
        } else if restored_items.is_empty() {
            "no_changes_needed".to_string()
        } else {
            "partial".to_string()
        };

        let message = if success {
            format!(
                "Restoration completed successfully. {} items restored.",
                restored_items.len()
            )
        } else if restored_items.is_empty() && !failed_items.is_empty() {
            format!(
                "Restoration failed. {} errors encountered.",
                failed_items.len()
            )
        } else {
            format!(
                "Partial restoration. {} restored, {} failed, {} warnings.",
                restored_items.len(),
                failed_items.len(),
                warnings.len()
            )
        };

        self.write_log(&format!(
            "Restoration finished: success={}, status={}, restored={}, failed={}, warnings={}",
            success,
            status,
            restored_items.len(),
            failed_items.len(),
            warnings.len()
        ))
        .await;

        Ok(RestorationResult {
            success,
            status,
            restored_items,
            failed_items,
            warnings,
            current_ip,
            original_ip: backup.public_ip.clone(),
            verification_passed,
            message,
        })
    }

    async fn restore_adapter(&self, adapter: &AdapterInfo) -> Result<String, String> {
        if cfg!(target_os = "windows") {
            self.restore_adapter_windows(adapter).await
        } else if cfg!(target_os = "macos") {
            self.restore_adapter_macos(adapter).await
        } else {
            self.restore_adapter_linux(adapter).await
        }
    }

    async fn restore_adapter_windows(&self, adapter: &AdapterInfo) -> Result<String, String> {
        match adapter.ip_mode {
            IpMode::Dhcp => {
                let output = Command::new("netsh")
                    .args([
                        "interface",
                        "ip",
                        "set",
                        "address",
                        &adapter.name,
                        "dhcp",
                    ])
                    .output()
                    .await
                    .map_err(|e| format!("Failed to execute netsh: {}", e))?;

                if !output.status.success() {
                    let stderr = String::from_utf8_lossy(&output.stderr);
                    if stderr.contains("requires elevation") || stderr.contains("administrador") {
                        return Err("Administrator privileges required".to_string());
                    }
                    return Err(format!("netsh failed: {}", stderr));
                }

                let _ = Command::new("netsh")
                    .args([
                        "interface",
                        "ip",
                        "set",
                        "dns",
                        &adapter.name,
                        "dhcp",
                    ])
                    .output()
                    .await;

                Ok("Set to DHCP".to_string())
            }
            IpMode::Static => {
                if let Some(ref ip) = adapter.ipv4_address {
                    let mut args = vec![
                        "interface", "ip", "set", "address", &adapter.name, "static", ip,
                    ];

                    if let Some(ref mask) = adapter.ipv4_mask {
                        args.push(mask);
                    }

                    if let Some(ref gw) = adapter.ipv4_gateway {
                        args.push(gw);
                    }

                    let output = Command::new("netsh")
                        .args(&args)
                        .output()
                        .await
                        .map_err(|e| format!("Failed to execute netsh: {}", e))?;

                    if !output.status.success() {
                        let stderr = String::from_utf8_lossy(&output.stderr);
                        if stderr.contains("requires elevation") || stderr.contains("administrador")
                        {
                            return Err("Administrator privileges required".to_string());
                        }
                        return Err(format!("netsh failed: {}", stderr));
                    }

                    for dns in &adapter.ipv4_dns {
                        let _ = Command::new("netsh")
                            .args([
                                "interface", "ip", "set", "dns", &adapter.name, "static", dns,
                            ])
                            .output()
                            .await;
                    }

                    Ok(format!("Set to static IP: {}", ip))
                } else {
                    Err("No IP address in backup".to_string())
                }
            }
            IpMode::Unknown => {
                Err("Unknown IP mode in backup, cannot restore".to_string())
            }
        }
    }

    async fn restore_adapter_linux(&self, adapter: &AdapterInfo) -> Result<String, String> {
        match adapter.ip_mode {
            IpMode::Dhcp => {
                let output = Command::new("sudo")
                    .args(["dhclient", "-r", &adapter.name])
                    .output()
                    .await
                    .map_err(|e| format!("Failed to execute dhclient: {}", e))?;

                if !output.status.success() {
                    let _ = Command::new("nmcli")
                        .args([
                            "connection",
                            "modify",
                            &adapter.name,
                            "ipv4.method",
                            "auto",
                        ])
                        .output()
                        .await;

                    let _ = Command::new("nmcli")
                        .args(["connection", "up", &adapter.name])
                        .output()
                        .await;
                }

                Ok("Set to DHCP".to_string())
            }
            IpMode::Static => {
                if let Some(ref ip) = adapter.ipv4_address {
                    let cidr = format!("{}/24", ip);

                    let _ = Command::new("sudo")
                        .args([
                            "ip", "addr", "flush", "dev", &adapter.name,
                        ])
                        .output()
                        .await;

                    let mut args = vec!["addr", "add", &cidr, "dev", &adapter.name];
                    if let Some(ref gw) = adapter.ipv4_gateway {
                        args.push("gw");
                        args.push(gw);
                    }

                    let output = Command::new("sudo")
                        .args(&args)
                        .output()
                        .await
                        .map_err(|e| format!("Failed to set IP: {}", e))?;

                    if !output.status.success() {
                        return Err("Failed to set static IP".to_string());
                    }

                    for dns in &adapter.ipv4_dns {
                        let _ = Command::new("sudo")
                            .args([
                                "resolvectl", "dns", &adapter.name, dns,
                            ])
                            .output()
                            .await;
                    }

                    Ok(format!("Set to static IP: {}", ip))
                } else {
                    Err("No IP address in backup".to_string())
                }
            }
            IpMode::Unknown => {
                Err("Unknown IP mode in backup, cannot restore".to_string())
            }
        }
    }

    async fn restore_adapter_macos(&self, adapter: &AdapterInfo) -> Result<String, String> {
        let service = &adapter.friendly_name;

        match adapter.ip_mode {
            IpMode::Dhcp => {
                let output = Command::new("networksetup")
                    .args(["-setdhcp", service])
                    .output()
                    .await
                    .map_err(|e| format!("Failed to set DHCP: {}", e))?;

                if !output.status.success() {
                    let stderr = String::from_utf8_lossy(&output.stderr);
                    if stderr.contains("permission") || stderr.contains("root") {
                        return Err("Administrator privileges required".to_string());
                    }
                    return Err(format!("networksetup failed: {}", stderr));
                }

                Ok("Set to DHCP".to_string())
            }
            IpMode::Static => {
                if let Some(ref ip) = adapter.ipv4_address {
                    let mask = adapter.ipv4_mask.as_deref().unwrap_or("255.255.255.0");
                    let gw = adapter.ipv4_gateway.as_deref().unwrap_or("");

                    let output = Command::new("networksetup")
                        .args([
                            "-setmanual", service, ip, mask, gw,
                        ])
                        .output()
                        .await
                        .map_err(|e| format!("Failed to set static: {}", e))?;

                    if !output.status.success() {
                        let stderr = String::from_utf8_lossy(&output.stderr);
                        if stderr.contains("permission") || stderr.contains("root") {
                            return Err("Administrator privileges required".to_string());
                        }
                        return Err(format!("networksetup failed: {}", stderr));
                    }

                    for dns in &adapter.ipv4_dns {
                        let _ = Command::new("networksetup")
                            .args(["-setdnsservers", service, dns])
                            .output()
                            .await;
                    }

                    Ok(format!("Set to static IP: {}", ip))
                } else {
                    Err("No IP address in backup".to_string())
                }
            }
            IpMode::Unknown => {
                Err("Unknown IP mode in backup, cannot restore".to_string())
            }
        }
    }

    async fn restore_proxy(&self, proxy: &ProxyConfig) -> Result<String, String> {
        if cfg!(target_os = "windows") {
            let enable_value = if proxy.enabled { "1" } else { "0" };
            let output = Command::new("reg")
                .args([
                    "add",
                    "HKCU\\Software\\Microsoft\\Windows\\CurrentVersion\\Internet Settings",
                    "/v",
                    "ProxyEnable",
                    "/t",
                    "REG_DWORD",
                    "/d",
                    enable_value,
                    "/f",
                ])
                .output()
                .await
                .map_err(|e| format!("Failed to set proxy: {}", e))?;

            if !output.status.success() {
                return Err("Failed to update proxy setting".to_string());
            }

            if let Some(ref server) = proxy.server {
                let proxy_str = match &proxy.port {
                    Some(port) => format!("{}:{}", server, port),
                    None => server.clone(),
                };

                let _ = Command::new("reg")
                    .args([
                        "add",
                        "HKCU\\Software\\Microsoft\\Windows\\CurrentVersion\\Internet Settings",
                        "/v",
                        "ProxyServer",
                        "/t",
                        "REG_SZ",
                        "/d",
                        &proxy_str,
                        "/f",
                    ])
                    .output()
                    .await;
            }

            Ok(format!(
                "Proxy {}",
                if proxy.enabled {
                    "enabled"
                } else {
                    "disabled"
                }
            ))
        } else if cfg!(target_os = "macos") {
            let service = "Wi-Fi";

            if proxy.enabled {
                if let Some(ref server) = proxy.server {
                    let port = proxy.port.as_deref().unwrap_or("8080");
                    let _ = Command::new("networksetup")
                        .args(["-setwebproxystate", service, "on", server, port])
                        .output()
                        .await;
                }
            } else {
                let _ = Command::new("networksetup")
                    .args(["-setwebproxystate", service, "off"])
                    .output()
                    .await;
            }

            Ok(format!(
                "Proxy {}",
                if proxy.enabled {
                    "enabled"
                } else {
                    "disabled"
                }
            ))
        } else {
            if proxy.enabled {
                if let Some(ref server) = proxy.server {
                    let port = proxy.port.as_deref().unwrap_or("8080");
                    let proxy_str = format!("http://{}:{}", server, port);
                    std::env::set_var("http_proxy", &proxy_str);
                    std::env::set_var("https_proxy", &proxy_str);
                }
            } else {
                std::env::remove_var("http_proxy");
                std::env::remove_var("https_proxy");
            }

            Ok(format!(
                "Proxy {} (environment)",
                if proxy.enabled {
                    "enabled"
                } else {
                    "disabled"
                }
            ))
        }
    }

    fn verify_restoration(&self, backup: &NetworkSnapshot, current: &NetworkSnapshot) -> bool {
        let mut all_match = true;

        for backup_adapter in &backup.adapters {
            if let Some(current_adapter) = current
                .adapters
                .iter()
                .find(|a| a.name == backup_adapter.name)
            {
                if backup_adapter.ip_mode != IpMode::Unknown {
                    if current_adapter.ipv4_address != backup_adapter.ipv4_address {
                        warn!(
                            "Verification: adapter {} IP mismatch: expected {:?}, got {:?}",
                            backup_adapter.name,
                            backup_adapter.ipv4_address,
                            current_adapter.ipv4_address
                        );
                        all_match = false;
                    }

                    if current_adapter.ip_mode != backup_adapter.ip_mode {
                        warn!(
                            "Verification: adapter {} mode mismatch: expected {:?}, got {:?}",
                            backup_adapter.name, backup_adapter.ip_mode, current_adapter.ip_mode
                        );
                        all_match = false;
                    }
                }
            }
        }

        if backup.proxy.enabled != current.proxy.enabled {
            warn!(
                "Verification: proxy state mismatch: expected {}, got {}",
                backup.proxy.enabled, current.proxy.enabled
            );
            all_match = false;
        }

        all_match
    }
}
