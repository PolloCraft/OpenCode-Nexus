use clap::{Parser, Subcommand};
use colored::Colorize;
use oplire_reset::{ProxyConfig, AppConfig};
use std::fs;
use std::path::PathBuf;
use std::process::Command;

const VERSION: &str = "4.0.0";

#[derive(Parser, Debug)]
#[command(name = "oplire")]
#[command(version = VERSION)]
#[command(about = "Oplire - Sistema de Rotacion de IP y Proxy Profesional", long_about = None)]
struct Cli {
    #[arg(short, long, global = true)]
    verbose: bool,

    #[arg(long, global = true)]
    dry_run: bool,

    #[command(subcommand)]
    command: Commands,
}

#[derive(Subcommand, Debug)]
enum Commands {
    Status {
        #[arg(long)]
        json: bool,
    },
    Reset {},
    QuickReset {},
    Install {
        #[command(subcommand)]
        target: InstallTarget,
    },
    Stop {},
    About {},
    Proxy {
        #[arg(long, default_value = "127.0.0.1:8080")]
        listen: String,
        #[arg(long, default_value = "http://localhost:3000")]
        upstream: String,
        #[arg(long)]
        api_key: Option<String>,
        #[arg(long, default_value = "3")]
        max_retries: u32,
        #[arg(long, default_value = "5000")]
        warp_delay: u64,
    },
    Connect {
        #[command(subcommand)]
        target: ConnectTarget,
    },
    Watch {
        #[arg(long, default_value = "http://localhost:3000")]
        upstream: String,
        #[arg(long, default_value = "3")]
        max_retries: u32,
        #[arg(long, default_value = "5000")]
        warp_delay: u64,
    },
    Daemon {
        #[arg(long, default_value = "127.0.0.1:8080")]
        listen: String,
        #[arg(long, default_value = "http://localhost:3000")]
        upstream: String,
        #[arg(long)]
        api_key: Option<String>,
        #[arg(long, default_value = "3")]
        max_retries: u32,
        #[arg(long, default_value = "5000")]
        warp_delay: u64,
    },
    Config {
        #[command(subcommand)]
        action: ConfigAction,
    },
    Doctor {},
    Setup {},
    Models {
        #[arg(long, default_value = "http://localhost:3000")]
        upstream: String,
    },
    Dashboard {
        #[arg(long, default_value = "127.0.0.1:8080")]
        listen: String,
        #[arg(long, default_value = "http://localhost:3000")]
        upstream: String,
        #[arg(long)]
        api_key: Option<String>,
        #[arg(long, default_value = "3")]
        max_retries: u32,
        #[arg(long, default_value = "5000")]
        warp_delay: u64,
    },
    SetupDesktop {
        #[arg(long, default_value = "127.0.0.1:8080")]
        listen: String,
    },
    RestoreDesktop {},
    DesktopStatus {},
    FixSessions {},
    SessionsStatus {},
    SessionsList {},
    SessionDetail {
        #[arg(long)]
        id: Option<String>,
    },
}

#[derive(Subcommand, Debug)]
enum InstallTarget {
    Warp {},
    Opencode {},
    ClaudeCode {},
    All {},
}

#[derive(Subcommand, Debug)]
enum ConnectTarget {
    ClaudeCode {
        #[arg(long, default_value = "127.0.0.1:8080")]
        listen: String,
        #[arg(long, default_value = "http://localhost:3000")]
        upstream: String,
        #[arg(long)]
        api_key: Option<String>,
        #[arg(long, default_value = "3")]
        max_retries: u32,
        #[arg(long, default_value = "5000")]
        warp_delay: u64,
        #[arg(long)]
        model: Option<String>,
        #[arg(long)]
        system_prompt: Option<String>,
        #[arg(last = true)]
        claude_args: Vec<String>,
    },
    Desktop {
        #[arg(long, default_value = "127.0.0.1:8080")]
        listen: String,
        #[arg(long, default_value = "3")]
        max_retries: u32,
        #[arg(long, default_value = "5000")]
        warp_delay: u64,
    },
}

#[derive(Subcommand, Debug)]
enum ConfigAction {
    Show {},
    Set {
        #[arg(long)]
        key: Option<String>,
        #[arg(long, default_value = "127.0.0.1:8080")]
        listen: String,
        #[arg(long, default_value = "http://localhost:3000")]
        upstream: String,
        #[arg(long, default_value = "3")]
        max_retries: u32,
        #[arg(long, default_value = "5000")]
        warp_delay: u64,
    },
    Reset {},
}

fn config_path() -> PathBuf {
    if cfg!(target_os = "windows") {
        if let Ok(appdata) = std::env::var("APPDATA") {
            let mut p = PathBuf::from(appdata);
            p.push("oplire");
            p.push("config.json");
            return p;
        }
    } else if cfg!(target_os = "macos") {
        if let Ok(home) = std::env::var("HOME") {
            let mut p = PathBuf::from(home);
            p.push("Library");
            p.push("Application Support");
            p.push("oplire");
            p.push("config.json");
            return p;
        }
    }

    if let Ok(xdg) = std::env::var("XDG_CONFIG_HOME") {
        let mut p = PathBuf::from(xdg);
        p.push("oplire");
        p.push("config.json");
        return p;
    }

    if let Ok(home) = std::env::var("HOME") {
        let mut p = PathBuf::from(home);
        p.push(".config");
        p.push("oplire");
        p.push("config.json");
        return p;
    }

    PathBuf::from("oplire/config.json")
}

fn load_config() -> AppConfig {
    let path = config_path();
    if path.exists() {
        if let Ok(content) = fs::read_to_string(&path) {
            if let Ok(config) = serde_json::from_str(&content) {
                return config;
            }
        }
    }
    AppConfig::default()
}

fn save_config(config: &AppConfig) -> Result<(), String> {
    let path = config_path();
    if let Some(parent) = path.parent() {
        fs::create_dir_all(parent).map_err(|e| e.to_string())?;
    }
    let content = serde_json::to_string_pretty(config).map_err(|e| e.to_string())?;
    fs::write(&path, content).map_err(|e| e.to_string())?;
    Ok(())
}

fn find_opencode_desktop_exe() -> Option<String> {
    let candidates = if cfg!(target_os = "windows") {
        vec![
            format!("{}\\AppData\\Local\\Programs\\@opencode-aidesktop\\OpenCode.exe",
                std::env::var("USERPROFILE").unwrap_or_default()),
            format!("{}\\AppData\\Local\\@opencode-aidesktop\\OpenCode.exe",
                std::env::var("USERPROFILE").unwrap_or_default()),
            "C:\\Program Files\\@opencode-aidesktop\\OpenCode.exe".to_string(),
            "C:\\Program Files (x86)\\@opencode-aidesktop\\OpenCode.exe".to_string(),
        ]
    } else if cfg!(target_os = "macos") {
        vec![
            "/Applications/OpenCode.app/Contents/MacOS/OpenCode".to_string(),
            format!("{}/Applications/OpenCode.app/Contents/MacOS/OpenCode",
                std::env::var("HOME").unwrap_or_default()),
        ]
    } else {
        vec![
            "/usr/bin/opencode-desktop".to_string(),
            "/usr/local/bin/opencode-desktop".to_string(),
            format!("{}/.local/bin/opencode-desktop",
                std::env::var("HOME").unwrap_or_default()),
        ]
    };

    for path in &candidates {
        if std::path::Path::new(path).exists() {
            return Some(path.clone());
        }
    }
    None
}

fn check_warp_installed() -> bool {
    Command::new("warp-cli").arg("--version").output().is_ok()
}

fn check_claude_installed() -> bool {
    Command::new("claude").arg("--version").output().is_ok()
}

fn check_opencode_installed() -> bool {
    Command::new("opencode").arg("--version").output().is_ok()
        || Command::new("opencode").arg("--help").output().is_ok()
}

fn check_opencode_running(base_url: &str) -> bool {
    let url = format!("{}/v1/models", base_url.trim_end_matches('/'));
    reqwest::blocking::Client::new()
        .get(&url)
        .timeout(std::time::Duration::from_secs(3))
        .send()
        .map(|r| r.status().is_success())
        .unwrap_or(false)
}

fn check_node_installed() -> bool {
    Command::new("node").arg("--version").output().is_ok()
}

fn run_command(cmd: &str, args: &[&str], dry_run: bool, verbose: bool) -> Result<String, String> {
    if dry_run {
        if verbose {
            eprintln!(
                "{} Would execute: {} {}",
                "[DRY-RUN]".cyan(),
                cmd,
                args.join(" ")
            );
        } else {
            eprintln!("{} {} {}", "[DRY-RUN]".cyan(), cmd, args.join(" "));
        }
        Ok(format!(
            "[DRY-RUN] Would execute: {} {}",
            cmd,
            args.join(" ")
        ))
    } else {
        let output = Command::new(cmd)
            .args(args)
            .output()
            .map_err(|e| e.to_string())?;

        if output.status.success() {
            Ok(String::from_utf8_lossy(&output.stdout).to_string())
        } else {
            Err(String::from_utf8_lossy(&output.stderr).to_string())
        }
    }
}

fn run_sudo_command(cmd: &str, dry_run: bool, verbose: bool) -> Result<String, String> {
    if cfg!(target_os = "windows") {
        return run_command("net", &["session"], dry_run, verbose);
    }

    if dry_run {
        if verbose {
            eprintln!("{} Would execute: sudo {}", "[DRY-RUN]".cyan(), cmd);
        } else {
            eprintln!("{} sudo {}", "[DRY-RUN]".cyan(), cmd);
        }
        Ok(format!("[DRY-RUN] Would execute: sudo {}", cmd))
    } else {
        let output = Command::new("sudo")
            .arg("-S")
            .arg("-n")
            .arg("-k")
            .arg("-v")
            .output()
            .map_err(|e| e.to_string())?;

        if !output.status.success() {
            return Err("sudo requires password or -n flag failed".to_string());
        }

        let output = Command::new("sudo")
            .arg("-S")
            .arg("sh")
            .arg("-c")
            .arg(cmd)
            .output()
            .map_err(|e| e.to_string())?;

        if output.status.success() {
            Ok(String::from_utf8_lossy(&output.stdout).to_string())
        } else {
            Err(String::from_utf8_lossy(&output.stderr).to_string())
        }
    }
}

fn run_interactive(cmd: &str, args: &[&str]) -> Result<(), String> {
    let status = Command::new(cmd)
        .args(args)
        .status()
        .map_err(|e| e.to_string())?;

    if status.success() {
        Ok(())
    } else {
        Err(format!("{} exited with {}", cmd, status))
    }
}

fn fetch_models(upstream: &str) -> Result<Vec<(String, String)>, String> {
    let models_url = format!("{}/v1/models", upstream.trim_end_matches('/'));

    let resp = reqwest::blocking::Client::new()
        .get(&models_url)
        .timeout(std::time::Duration::from_secs(10))
        .send()
        .map_err(|e| e.to_string())?;

    if !resp.status().is_success() {
        return Err(format!("HTTP {}", resp.status()));
    }

    let data = resp.json::<serde_json::Value>().map_err(|e| e.to_string())?;

    let models = data
        .get("data")
        .and_then(|v| v.as_array())
        .ok_or_else(|| "No models in response".to_string())?;

    Ok(models
        .iter()
        .filter_map(|m| {
            let id = m.get("id").and_then(|v| v.as_str())?.to_string();
            let name = match m.get("name")
                .or_else(|| m.get("display_name"))
                .and_then(|v| v.as_str())
            {
                Some(n) => n.to_string(),
                None => id.replace('-', " ")
                    .split_whitespace()
                    .map(|w| {
                        let mut c = w.chars();
                        match c.next() {
                            None => String::new(),
                            Some(ch) => format!(
                                "{}{}",
                                ch.to_uppercase().collect::<String>(),
                                c.as_str()
                            ),
                        }
                    })
                    .collect::<Vec<_>>()
                    .join(" "),
            };
            Some((id, name))
        })
        .collect())
}

fn select_model_interactively(models: &[(String, String)]) -> Option<String> {
    use std::io::{self, Write};

    if models.is_empty() {
        return None;
    }

    println!();
    println!("{}", "Available models:".bold());
    println!();

    for (i, (id, name)) in models.iter().enumerate() {
        println!("  {} {} — {}", format!("[{}]", i + 1).dimmed(), id.bold().yellow(), name);
    }

    println!();
    print!("{} Select model (1-{}): ", "→".cyan(), models.len());
    io::stdout().flush().ok()?;

    let mut input = String::new();
    io::stdin().read_line(&mut input).ok()?;
    let num: usize = input.trim().parse().ok()?;

    if num >= 1 && num <= models.len() {
        Some(models[num - 1].0.clone())
    } else {
        None
    }
}

fn print_banner() {
    println!(
        "{}",
        r#"
  ___      ___    _       ___     ___     ___   
 / _ \    | _ \  | |     |_ _|   | _ \   | __|  
| (_) |   |  _/  | |__    | |    |   /   | _|   
 \___/   _|_|_   |____|  |___|   |_|_\   |___|  
_|"""""|_| """ |_|"""""|_|"""""|_|"""""|_|"""""| 
"`-0-0-'"`-0-0-'"`-0-0-'"`-0-0-'"`-0-0-'"`-0-0-'
"#
        .bold()
        .cyan()
    );
}

fn print_step(num: usize, text: &str) {
    println!("  {} {}", format!("[{}/5]", num).dimmed(), text.bold());
}

fn print_success(text: &str) {
    println!("  {} {}", "✓".green().bold(), text);
}

fn print_fail(text: &str) {
    println!("  {} {}", "✗".red().bold(), text);
}

fn print_info_formatted(label: &str, desc: &str) {
    println!("  {} {} — {}", "→".cyan(), label.bold(), desc.dimmed());
}

fn main() {
    tracing_subscriber::fmt()
        .with_env_filter(
            tracing_subscriber::EnvFilter::from_default_env()
                .add_directive(tracing::Level::INFO.into()),
        )
        .init();

    let cli = Cli::parse();

    if cli.verbose {
        eprintln!("{} Verbose mode enabled", "[DEBUG]".yellow());
    }

    if cli.dry_run {
        eprintln!(
            "{} Dry run mode - no changes will be made",
            "[DRY-RUN]".cyan()
        );
    }

    let warp_installed = check_warp_installed();

    match &cli.command {
        Commands::Dashboard {
            listen,
            upstream,
            api_key,
            max_retries,
            warp_delay,
        } => {
            print_banner();
            println!("{}", "Modo Dashboard de Oplire".bold().green());
            println!();
            println!("{} Escuchando en:      {}", "→".green(), listen.bold());
            println!("{} Upstream:            {}", "→".green(), upstream.bold());
            println!("{} URL del Dashboard:   {}", "→".green(), format!("http://{}", listen).bold().yellow());
            println!();
            println!("{}", "Abra su navegador para acceder al panel de control".dimmed());
            println!("{} Presione Ctrl+C para detener", "Consejo:".cyan());
            println!();

            let config = ProxyConfig {
                listen_addr: listen.clone(),
                opencode_base_url: upstream.clone(),
                opencode_api_key: api_key.clone(),
                max_retries: *max_retries,
                warp_reset_delay_ms: *warp_delay,
            };

            let rt = tokio::runtime::Runtime::new().unwrap();
            if let Err(e) = rt.block_on(async {
                oplire_reset::proxy::start_proxy_server(config).await
            }) {
                eprintln!("{} Dashboard error: {}", "[ERROR]".red(), e);
                std::process::exit(1);
            }
        }

        Commands::SetupDesktop { listen } => {
            print_banner();
            println!("{}", "Configuracion del Bypass de OpenCode Desktop".bold().green());
            println!();

            let bypass = oplire_reset::bypass::DesktopBypass::new();
            let status = bypass.status();

            println!("{} Ruta de config:   {}", "→".cyan(), status.config_path.bold());
            println!("{} Config encontrada: {}", "→".cyan(), if status.config_found { "Si".green().bold() } else { "No".red().bold() });
            println!("{} En Proxy:         {}", "→".cyan(), if status.is_proxied { "Si".green().bold() } else { "No".yellow().bold() });
            if status.backup_exists {
                println!("{} Respaldo:         {}", "→".cyan(), "Si".green().bold());
            }
            println!();

            if status.is_proxied {
                println!("{} OpenCode Desktop ya esta configurado para usar el proxy de oplire", "[INFO]".green());
                println!("{} Direccion del proxy: {}", "→".cyan(), status.api_base_url.bold());
                println!();
                println!("{} Si cambio el puerto del proxy, ejecute:", "Consejo:".cyan());
                println!("  {}", "oplire setup-desktop --listen <nuevo-puerto>".bold().yellow());
                return;
            }

            println!("{} Configurando OpenCode Desktop para enrutar a traves del proxy...", "→".cyan());
            println!("{} Direccion del proxy: http://{}", "→".cyan(), listen.bold().yellow());
            println!();

            match bypass.enable(listen) {
                Ok(msg) => {
                    println!("{}", "Configuracion completada!".green().bold());
                    println!();
                    for line in msg.lines() {
                        println!("  {}", line);
                    }
                    println!();
                    println!("{}", "Siguientes pasos:".bold());
                    println!("  1. {}", "oplire dashboard".bold().yellow());
                    println!("  2. {}", "Reiniciar OpenCode Desktop".bold().yellow());
                    println!();
                    println!("{}", "La aplicacion de escritorio ahora usara el proxy de oplire para todas las llamadas API.".dimmed());
                    println!("{}", "Los limites se manejaran automaticamente mediante la rotacion de IP WARP.".dimmed());
                }
                Err(e) => {
                    eprintln!("{} Configuracion fallida: {}", "[ERROR]".red(), e);
                    std::process::exit(1);
                }
            }
        }

        Commands::RestoreDesktop {} => {
            print_banner();
            println!("{}", "Restaurar Configuracion de OpenCode Desktop".bold().cyan());
            println!();

            let bypass = oplire_reset::bypass::DesktopBypass::new();

            match bypass.disable() {
                Ok(msg) => {
                    println!("{}", "Configuracion restaurada!".green().bold());
                    println!();
                    for line in msg.lines() {
                        println!("  {}", line);
                    }
                }
                Err(e) => {
                    eprintln!("{} Restauracion fallida: {}", "[ERROR]".red(), e);
                    println!("{} No se encontro respaldo. Puede que necesite editar la config manualmente.", "Consejo:".cyan());
                }
            }
        }

        Commands::DesktopStatus {} => {
            print_banner();
            println!("{}", "Estado del Bypass de OpenCode Desktop".bold().cyan());
            println!();

            let bypass = oplire_reset::bypass::DesktopBypass::new();
            let status = bypass.status();

            println!("{} Ruta de config:      {}", "→".cyan(), status.config_path.bold());
            println!("{} Config encontrada:   {}", "→".cyan(), if status.config_found { "Si".green().bold() } else { "No".red().bold() });
            println!("{} Usando proxy:        {}", "→".cyan(), if status.is_proxied { "Si".green().bold() } else { "No".yellow().bold() });
            println!("{} URL Base API:        {}", "→".cyan(), if status.api_base_url.is_empty() { "(ninguna)".dimmed().to_string() } else { status.api_base_url.bold().to_string() });
            println!("{} Clave API:           {}", "→".cyan(), if status.api_key.is_empty() { "(ninguna)".dimmed().to_string() } else { status.api_key.bold().to_string() });
            println!("{} Respaldo existe:     {}", "→".cyan(), if status.backup_exists { "Si".green().bold() } else { "No".dimmed() });
            println!();

            if !status.config_found {
                println!("{}", "OpenCode Desktop no detectado.".yellow().bold());
                println!("{} Asegurese de que OpenCode Desktop este instalado y se haya ejecutado al menos una vez.", "Consejo:".cyan());
                println!();
                println!("  {}", "oplire setup-desktop".bold().yellow());
            } else if status.is_proxied {
                println!("{}", "OpenCode Desktop esta configurado correctamente!".green().bold());
                println!("{} Todas las llamadas API del escritorio pasaran por el proxy de oplire.", "→".green());
                println!("{} Los limites se manejaran automaticamente.", "→".green());
                println!();
                println!("{} Para restaurar la config original:", "Consejo:".cyan());
                println!("  {}", "oplire restore-desktop".bold().yellow());
            } else {
                println!("{}", "OpenCode Desktop NO esta configurado para el proxy de oplire.".yellow().bold());
                println!();
                println!("{} Para activar el bypass:", "Consejo:".cyan());
                println!("  1. {}", "oplire dashboard".bold().yellow());
                println!("  2. {}", "oplire setup-desktop".bold().yellow());
            }
        }

        Commands::Models { upstream } => {
            print_banner();
            println!("{}", "Modelos Disponibles".bold().cyan());
            println!();
            println!("{} Obteniendo modelos de {}...", "→".cyan(), upstream.bold());
            println!();

            let models_url = format!("{}/v1/models", upstream.trim_end_matches('/'));

            match reqwest::blocking::Client::new()
                .get(&models_url)
                .timeout(std::time::Duration::from_secs(10))
                .send()
            {
                Ok(resp) if resp.status().is_success() => {
                    match resp.json::<serde_json::Value>() {
                        Ok(data) => {
                            if let Some(models) = data.get("data").and_then(|v| v.as_array()) {
                                if models.is_empty() {
                                    println!("{} No models found", "[INFO]".yellow());
                                    return;
                                }

                                println!("  {}  {:<30}  {}", "#".dimmed(), "ID".bold(), "Name".bold());
                                println!("  {}", "─".repeat(60).dimmed());

                                for (i, m) in models.iter().enumerate() {
                                    let id = m.get("id").and_then(|v| v.as_str()).unwrap_or("?");
                                    let name: String = match m.get("name")
                                        .or_else(|| m.get("display_name"))
                                        .and_then(|v| v.as_str())
                                    {
                                        Some(n) => n.to_string(),
                                        None => id.replace('-', " ").split_whitespace()
                                            .map(|w| {
                                                let mut c = w.chars();
                                                match c.next() {
                                                    None => String::new(),
                                                    Some(ch) => format!("{}{}", ch.to_uppercase().collect::<String>(), c.as_str()),
                                                }
                                            })
                                            .collect::<Vec<_>>().join(" "),
                                    };

                                    println!("  {}  {:<30}  {}",
                                        format!("[{}]", i + 1).dimmed(),
                                        id.yellow(),
                                        name
                                    );
                                }

                                println!();
                                println!("{}", "Usage:".bold());
                                println!("  {}", "oplire connect claude-code --model <id>".bold().yellow());
                                println!();
                                println!("{}", "Examples:".bold());
                                for m in models.iter().take(3) {
                                    let id = m.get("id").and_then(|v| v.as_str()).unwrap_or("");
                                    if !id.is_empty() {
                                        println!("  {}", format!("oplire connect claude-code --model {}", id).dimmed());
                                    }
                                }
                            } else {
                                println!("{} No 'data' field in response", "[ERROR]".red());
                            }
                        }
                        Err(e) => {
                            println!("{} Failed to parse response: {}", "[ERROR]".red(), e);
                        }
                    }
                }
                Ok(resp) => {
                    println!("{} Upstream returned status: {}", "[ERROR]".red(), resp.status());
                    println!("{} Is OpenCode Zen running on {}?", "Tip:".cyan(), upstream.bold());
                }
                Err(e) => {
                    println!("{} Failed to connect to {}", "[ERROR]".red(), upstream.bold());
                    println!("{} {}", "Error:".dimmed(), e.to_string().dimmed());
                    println!("{} Is OpenCode Zen running?", "Tip:".cyan());
                }
            }
        }

        Commands::Setup {} => {
            print_banner();
            println!("{}", "Bienvenido al Asistente de Configuracion de Oplire".bold().green());
            println!();
            println!("{}", "Esto verificara e instalara todos los componentes necesarios.".dimmed());
            println!();

            let mut steps_needed = Vec::new();

            if !check_node_installed() {
                steps_needed.push(("Node.js", "npm install -g npm", "Required for Claude Code and OpenCode"));
            }
            if !warp_installed {
                steps_needed.push(("Cloudflare WARP", "oplire install warp", "Required for rate limit reset"));
            }
            if !check_opencode_installed() {
                steps_needed.push(("OpenCode", "oplire install opencode", "AI coding assistant backend"));
            }
            if !check_claude_installed() {
                steps_needed.push(("Claude Code", "oplire install claudecode", "AI coding assistant CLI"));
            }

            if steps_needed.is_empty() {
                println!("{}", "Todo esta instalado!".green().bold());
                println!();
                println!("{} Ejecute para comenzar:", "Consejo:".cyan().bold());
                println!("  {}", "oplire connect claude-code".bold().yellow());
                return;
            }

            println!("{}", "Los siguientes componentes necesitan instalarse:".bold());
            println!();
            for (name, _, desc) in &steps_needed {
                print_info_formatted(name, desc);
            }
            println!();

            for (i, (name, _cmd, _)) in steps_needed.iter().enumerate() {
                println!();
                print_step(i + 1, &format!("Installing {}...", name));

                match *name {
                    "Node.js" => {
                        println!("  {} Node.js must be installed manually", "ℹ".yellow());
                        if cfg!(target_os = "windows") {
                            println!("  {}", "Download from https://nodejs.org/".dimmed());
                        } else {
                            println!("  {}", "curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.40.1/install.sh | bash".dimmed());
                        }
                        println!("  {}", "Then restart your terminal".dimmed());
                    }
                    "Cloudflare WARP" => {
                        let _ = run_interactive("oplire", &["install", "warp"]);
                    }
                    "OpenCode" => {
                        let _ = run_interactive("oplire", &["install", "opencode"]);
                    }
                    "Claude Code" => {
                        let _ = run_interactive("oplire", &["install", "claude-code"]);
                    }
                    _ => {}
                }
            }

            println!();
            println!("{}", "Setup complete!".green().bold());
                println!();
                println!("{}", "Next steps:".bold());
                println!("  1. {}", "oplire doctor".bold().yellow());
                println!("  2. {}", "oplire dashboard".bold().yellow());
                println!("  3. {}", "oplire connect claude-code".bold().yellow());
        }

        Commands::Install { target } => match target {
            InstallTarget::Warp {} => {
                print_banner();
                println!("{}", "Instalando Cloudflare WARP".bold().green());
                println!();

                if warp_installed {
                    println!("{} WARP ya esta instalado", "[INFO]".green());
                    println!("{} Ejecute `oplire reset` para renovar su IP", "Consejo:".cyan());
                    return;
                }

                if cfg!(target_os = "windows") {
                    println!("{} Descargando instalador de Cloudflare WARP...", "→".cyan());
                    let installer_url = "https://1111-releases.cloudflare.com/latest/Windows%20Cloudflare%20WARP%20Setup.exe";
                    let installer_path = std::env::temp_dir().join("Cloudflare-WARP-Setup.exe");

                    match reqwest::blocking::Client::new()
                        .get(installer_url)
                        .timeout(std::time::Duration::from_secs(120))
                        .send()
                    {
                        Ok(resp) if resp.status().is_success() => {
                            let bytes = resp.bytes().map_err(|e| e.to_string()).unwrap();
                            fs::write(&installer_path, bytes).unwrap();
                            println!("{} Running installer...", "→".cyan());
                            let _ = Command::new(&installer_path)
                                .args(["/S"])
                                .status();
                            println!("{}", "WARP installed!".green().bold());
                        }
                        Ok(resp) => {
                            println!("{} Download failed: {}", "[ERROR]".red(), resp.status());
                        }
                        Err(e) => {
                            println!("{} Download error: {}", "[ERROR]".red(), e);
                        }
                    }
                } else if cfg!(target_os = "linux") {
                    if let Ok(output) = Command::new("sh").arg("-c").arg("cat /etc/os-release").output() {
                        let os_release = String::from_utf8_lossy(&output.stdout);

                        if os_release.contains("arch") || os_release.contains("manjaro") {
                            print_step(1, "Installing cloudflare-warp-bin via yay...");
                            match run_interactive("yay", &["-S", "--noconfirm", "cloudflare-warp-bin"]) {
                                Ok(()) => print_success("WARP installed"),
                                Err(e) => print_fail(&format!("Installation failed: {}", e)),
                            }
                        } else if os_release.contains("ubuntu")
                            || os_release.contains("debian")
                            || os_release.contains("kali")
                        {
                            print_step(1, "Adding Cloudflare repository...");

                            let _ = run_sudo_command(
                                "rm -f /etc/apt/sources.list.d/cloudflare-warp.list",
                                cli.dry_run,
                                cli.verbose,
                            );

                            let _ = run_sudo_command(
                                "curl -fsSL https://pkg.cloudflareclient.com/pubkey.gpg | gpg --yes --dearmor --output /usr/share/keyrings/cloudflare-warp-archive-keyring.gpg",
                                cli.dry_run, cli.verbose,
                            );

                            let repo_codename = if os_release.contains("kali") {
                                "trixie"
                            } else {
                                "$(. /etc/os-release && printf '%s' \"$VERSION_CODENAME\")"
                            };

                            let repo_command = format!(
                                "echo \"deb [signed-by=/usr/share/keyrings/cloudflare-warp-archive-keyring.gpg] https://pkg.cloudflareclient.com/ {} main\" > /etc/apt/sources.list.d/cloudflare-client.list",
                                repo_codename
                            );
                            let _ = run_sudo_command(
                                &repo_command,
                                cli.dry_run, cli.verbose,
                            );

                            print_step(2, "Installing cloudflare-warp...");
                            let _ = run_sudo_command("apt update -qq && apt install -y -qq cloudflare-warp", cli.dry_run, cli.verbose);
                        } else if os_release.contains("fedora") {
                            print_step(1, "Installing cloudflare-warp via dnf...");
                            let _ = run_sudo_command("dnf install -y cloudflare-warp", cli.dry_run, cli.verbose);
                        } else {
                            println!("{} Unsupported OS. Install manually:", "Warning:".yellow());
                            println!("  {}", "https://developers.cloudflare.com/warp-client/get-started/linux/".dimmed());
                            return;
                        }
                    }
                } else if cfg!(target_os = "macos") {
                    println!("{} Installing via Homebrew...", "→".cyan());
                    let _ = run_interactive("brew", &["install", "--cask", "cloudflare-warp"]);
                }

                if check_warp_installed() {
                    println!();
                    println!("{}", "Next steps:".bold());
                    println!("  1. {}", "warp-cli connect".bold().yellow());
                    println!("  2. {}", "warp-cli status".bold().yellow());
                    println!("  3. {}", "oplire reset".bold().yellow());
                } else {
                    println!();
                    print_fail("WARP installation may have failed. Check output above.");
                }
            }

            InstallTarget::Opencode {} => {
                print_banner();
                println!("{}", "Installing OpenCode".bold().green());
                println!();

                if check_opencode_installed() {
                    println!("{} OpenCode is already installed", "[INFO]".green());
                    return;
                }

                if !check_node_installed() {
                    println!("{} Node.js is required but not found", "[ERROR]".red());
                    println!("{} Install Node.js first: https://nodejs.org/", "Fix:".cyan());
                    std::process::exit(1);
                }

                print_step(1, "Installing OpenCode via npm...");
                match run_interactive("npm", &["install", "-g", "opencode-ai"]) {
                    Ok(()) => {
                        print_success("OpenCode installed");
                        println!();
                        println!("{}", "Next steps:".bold());
                        println!("  1. {}", "opencode".bold().yellow());
                        println!("  2. {}", "oplire doctor".bold().yellow());
                        println!("  3. {}", "oplire dashboard".bold().yellow());
                    }
                    Err(e) => {
                        print_fail(&format!("Installation failed: {}", e));
                        println!();
                        println!("{} Try manually:", "Fix:".cyan());
                        println!("  {}", "npm install -g opencode-ai".bold().yellow());
                    }
                }
            }

            InstallTarget::ClaudeCode {} => {
                print_banner();
                println!("{}", "Installing Claude Code".bold().green());
                println!();

                if check_claude_installed() {
                    let version = run_command("claude", &["--version"], false, false)
                        .map(|v| v.trim().to_string())
                        .unwrap_or_else(|_| "unknown".to_string());
                    println!("{} Claude Code is already installed ({})", "[INFO]".green(), version.dimmed());
                    return;
                }

                if !check_node_installed() {
                    println!("{} Node.js is required but not found", "[ERROR]".red());
                    println!("{} Install Node.js first: https://nodejs.org/", "Fix:".cyan());
                    std::process::exit(1);
                }

                print_step(1, "Installing Claude Code via npm...");
                match run_interactive("npm", &["install", "-g", "@anthropic-ai/claude-code"]) {
                    Ok(()) => {
                        print_success("Claude Code installed");
                        println!();
                        println!("{}", "Next steps:".bold());
                        println!("  1. {}", "claude --version".bold().yellow());
                        println!("  2. {}", "oplire connect claude-code".bold().yellow());
                    }
                    Err(e) => {
                        print_fail(&format!("Installation failed: {}", e));
                        println!();
                        println!("{} Try manually:", "Fix:".cyan());
                        println!("  {}", "npm install -g @anthropic-ai/claude-code".bold().yellow());
                    }
                }
            }

            InstallTarget::All {} => {
                print_banner();
                println!("{}", "Installing All Components".bold().green());
                println!();

                print_step(1, "Checking Cloudflare WARP...");
                if check_warp_installed() {
                    print_success("WARP already installed");
                } else {
                    let _ = run_interactive("oplire", &["install", "warp"]);
                }

                print_step(2, "Checking OpenCode...");
                if check_opencode_installed() {
                    print_success("OpenCode already installed");
                } else {
                    let _ = run_interactive("oplire", &["install", "opencode"]);
                }

                print_step(3, "Checking Claude Code...");
                if check_claude_installed() {
                    print_success("Claude Code already installed");
                } else {
                    let _ = run_interactive("oplire", &["install", "claude-code"]);
                }

                println!();
                println!("{}", "All components installed!".green().bold());
                println!();
                println!("{}", "Run to get started:".bold());
                println!("  {}", "oplire dashboard".bold().yellow());
            }
        },

        Commands::Connect {
            target: ConnectTarget::ClaudeCode {
                listen,
                upstream,
                api_key,
                max_retries,
                warp_delay,
                model,
                system_prompt,
                claude_args,
            },
        } => {
            print_banner();
            println!("{}", "Puente de Claude Code".bold().green());
            println!();

            if !check_claude_installed() {
                eprintln!("{} Claude Code no encontrado en PATH", "[ERROR]".red());
                eprintln!("{} Instale: {}", "Correccion:".cyan(), "oplire install claude-code".bold().yellow());
                std::process::exit(1);
            }

            let selected_model = match model {
                Some(m) => m.clone(),
                None => {
                    println!("{} Fetching models from {}...", "→".cyan(), upstream.bold());
                    match fetch_models(upstream) {
                        Ok(models) => {
                            if models.is_empty() {
                                println!("{} No models found, using default", "[WARN]".yellow());
                                String::new()
                            } else {
                                match select_model_interactively(&models) {
                                    Some(id) => id,
                                    None => {
                                        println!("{} No selection made, using default", "[WARN]".yellow());
                                        String::new()
                                    }
                                }
                            }
                        }
                        Err(e) => {
                            println!("{} Failed to fetch models: {}", "[WARN]".yellow(), e);
                            println!("{} Starting without model selection", "Tip:".cyan());
                            String::new()
                        }
                    }
                }
            };

            let config = ProxyConfig {
                listen_addr: listen.clone(),
                opencode_base_url: upstream.clone(),
                opencode_api_key: api_key.clone(),
                max_retries: *max_retries,
                warp_reset_delay_ms: *warp_delay,
            };

            println!("{} Proxy:      {}", "→".green(), listen.bold());
            println!("{} Upstream:   {}", "→".green(), upstream.bold());
            println!("{} Auto-reset: {} (attempts: {})", "→".green(), "enabled".green().bold(), max_retries.to_string().bold());
            if !selected_model.is_empty() {
                println!("{} Model:     {}", "→".green(), selected_model.bold());
            }
            if let Some(sp) = system_prompt {
                println!("{} System:    {} chars", "→".green(), sp.len().to_string().bold());
            }
            println!();

            println!("{}", "Starting proxy server...".dimmed());

            let proxy_config = config.clone();
            let listen_clone = listen.clone();
            let model_clone = selected_model.clone();

            let proxy_handle = std::thread::spawn(move || {
                let rt = tokio::runtime::Runtime::new().unwrap();
                rt.block_on(async {
                    oplire_reset::proxy::start_proxy_server(proxy_config).await
                })
            });

            std::thread::sleep(std::time::Duration::from_millis(1500));

            println!("{}", "Launching Claude Code...".dimmed());
            println!();

            let mut cmd = Command::new("claude");
            cmd.env("ANTHROPIC_BASE_URL", format!("http://{}", listen_clone))
                .env("ANTHROPIC_API_KEY", "oplire-proxy-key");

            if !model_clone.is_empty() {
                cmd.env("ANTHROPIC_MODEL", &model_clone);
            }

            if let Some(sp) = system_prompt {
                cmd.env("CLAUDE_CODE_SYSTEM_PROMPT", sp);
            }

            if !claude_args.is_empty() {
                cmd.args(claude_args);
            }

            let status = cmd.status().map_err(|e| e.to_string()).unwrap_or_else(|_| {
                eprintln!("{} Failed to launch Claude Code", "[ERROR]".red());
                std::process::exit(1);
            });

            println!();
            println!("{} Claude Code exited with: {}", "Info:".cyan(), status.to_string().bold());
            println!("{} Shutting down proxy...", "→".green().dimmed());

            drop(proxy_handle);
        }

        Commands::Connect {
            target: ConnectTarget::Desktop {
                listen,
                max_retries,
                warp_delay,
            },
        } => {
            print_banner();
            println!("{}", "Puente de OpenCode Desktop".bold().green());
            println!();

            let desktop_path = find_opencode_desktop_exe();
            if let Some(ref path) = desktop_path {
                if !std::path::Path::new(path).exists() {
                    eprintln!("{} OpenCode Desktop no encontrado en: {}", "[ERROR]".red(), path);
                    std::process::exit(1);
                }
            } else {
                eprintln!("{} OpenCode Desktop no encontrado. Buscando en ubicaciones comunes.", "[ERROR]".red());
                std::process::exit(1);
            }

            println!("{} Configurando OpenCode Desktop para usar el proxy...", "Paso 1:".cyan().bold());

            let config_dir = std::env::var("APPDATA")
                .map(std::path::PathBuf::from)
                .unwrap_or_else(|_| std::path::PathBuf::from("."))
                .join("opencode");
            std::fs::create_dir_all(&config_dir).ok();

            let proxy_config = serde_json::json!({
                "$schema": "https://opencode.ai/config.json",
                "provider": {
                    "anthropic": {
                        "options": {
                            "baseURL": format!("http://{}", listen)
                        }
                    },
                    "openai": {
                        "options": {
                            "baseURL": format!("http://{}/v1", listen)
                        }
                    }
                }
            });

            let config_content = serde_json::to_string_pretty(&proxy_config).unwrap();
            println!("{} Provider config pointing to proxy", "  ✓".green());
            println!("    Anthropic → http://{}/v1/messages", listen);
            println!("    OpenAI    → http://{}/v1/chat/completions", listen);
            println!();

            println!("{} Starting oplire proxy on {}...", "Step 2:".cyan().bold(), listen);

            let config = ProxyConfig {
                listen_addr: listen.clone(),
                opencode_base_url: "http://localhost:3000".to_string(),
                opencode_api_key: None,
                max_retries: *max_retries,
                warp_reset_delay_ms: *warp_delay,
            };

            let proxy_handle = std::thread::spawn({
                let config = config.clone();
                move || {
                    let rt = tokio::runtime::Runtime::new().unwrap();
                    if let Err(e) = rt.block_on(async {
                        oplire_reset::proxy::start_proxy_server(config).await
                    }) {
                        eprintln!("{} Proxy error: {}", "[ERROR]".red(), e);
                    }
                }
            });

            std::thread::sleep(std::time::Duration::from_secs(2));

            println!("{} Launching OpenCode Desktop...", "Step 3:".cyan().bold());

            let mut cmd = std::process::Command::new(desktop_path.as_ref().unwrap());
            cmd.env("OPENCODE_CONFIG_CONTENT", &config_content);

            match cmd.spawn() {
                Ok(_) => {
                    println!("{} OpenCode Desktop launched!", "  ✓".green());
                    println!();
                    println!("{}", "OpenCode Desktop Bridge active!".bold().green());
                    println!("  All API calls from Desktop → oplire proxy → real API");
                    println!("  Auto WARP reset on 429 rate limits");
                    println!();
                    println!("{} Press Ctrl+C to stop", "Tip:".cyan());
                }
                Err(e) => {
                    eprintln!("{} Failed to launch OpenCode Desktop: {}", "[ERROR]".red(), e);
                    eprintln!("{} Falling back: Open OpenCode Desktop manually", "Fix:".cyan());
                    eprintln!("  The proxy is running on {} - configure Desktop manually", listen.bold());
                }
            }

            let _ = proxy_handle.join();
        }

        Commands::Watch {
            upstream,
            max_retries,
            warp_delay,
        } => {
            print_banner();
            println!("{}", "Modo Monitoreo de Oplire".bold().yellow());
            println!();
            println!("{} Monitoreando: {}", "→".green(), upstream.bold());
            println!("{} Auto-reset: {} (intentos: {})", "→".green(), "activado".green().bold(), max_retries.to_string().bold());
            println!();
            println!("{}", "Observando limites de velocidad 429...".dimmed());
            println!("{} Presione Ctrl+C para detener", "Consejo:".cyan());
            println!();

            let upstream_clone = upstream.clone();
            let max_retries_clone = *max_retries;
            let warp_delay_clone = *warp_delay;

            let rt = tokio::runtime::Runtime::new().unwrap();
            if let Err(e) = rt.block_on(async {
                oplire_reset::watch::start_watch_mode(
                    &upstream_clone,
                    max_retries_clone,
                    warp_delay_clone,
                )
                .await
            }) {
                eprintln!("{} Watch error: {}", "[ERROR]".red(), e);
                std::process::exit(1);
            }
        }

        Commands::Daemon {
            listen,
            upstream,
            api_key,
            max_retries,
            warp_delay,
        } => {
            print_banner();
            println!("{}", "Modo Demonio".bold().magenta());
            println!();
            println!("{} Escuchando:   {}", "→".green(), listen.bold());
            println!("{} Upstream:     {}", "→".green(), upstream.bold());
            println!("{} Auto-reset:   {} (intentos: {})", "→".green(), "activado".green().bold(), max_retries.to_string().bold());
            println!();
            println!("{}", "Ejecutando como demonio en segundo plano...".dimmed());
            println!("{} El proxy reseteara los limites automaticamente en silencio", "Consejo:".cyan());
            println!();

            let config = ProxyConfig {
                listen_addr: listen.clone(),
                opencode_base_url: upstream.clone(),
                opencode_api_key: api_key.clone(),
                max_retries: *max_retries,
                warp_reset_delay_ms: *warp_delay,
            };

            let rt = tokio::runtime::Runtime::new().unwrap();
            if let Err(e) = rt.block_on(async {
                oplire_reset::proxy::start_proxy_server(config).await
            }) {
                eprintln!("{} Daemon error: {}", "[ERROR]".red(), e);
                std::process::exit(1);
            }
        }

        Commands::Doctor {} => {
            print_banner();
            println!("{}", "Diagnostico del Sistema".bold().cyan());
            println!();

            let mut all_ok = true;
            let mut checks = Vec::new();

            if warp_installed {
                checks.push(("WARP CLI", "installed".to_string(), true));
            } else {
                checks.push(("WARP CLI", "NOT FOUND".to_string(), false));
                all_ok = false;
            }

            if check_claude_installed() {
                let version = run_command("claude", &["--version"], false, false)
                    .map(|v| v.trim().to_string())
                    .unwrap_or_else(|_| "unknown".to_string());
                checks.push(("Claude Code", format!("installed ({})", version), true));
            } else {
                checks.push(("Claude Code", "NOT FOUND".to_string(), false));
                all_ok = false;
            }

            if check_opencode_installed() {
                checks.push(("OpenCode", "installed".to_string(), true));
            } else {
                checks.push(("OpenCode", "NOT FOUND".to_string(), false));
                all_ok = false;
            }

            let config = load_config();
            let upstream = config.upstream.clone();
            if check_opencode_running(&upstream) {
                checks.push(("OpenCode Zen", format!("running ({})", upstream), true));
            } else {
                checks.push(("OpenCode Zen", format!("NOT REACHABLE ({})", upstream), false));
                all_ok = false;
            }

            let cfg_path = config_path();
            if cfg_path.exists() {
                checks.push(("Config file", format!("found ({})", cfg_path.display()), true));
            } else {
                checks.push(("Config file", "using defaults".to_string(), true));
            }

            if std::net::TcpListener::bind("127.0.0.1:8080").is_ok() {
                checks.push(("Port 8080", "available".to_string(), true));
            } else {
                checks.push(("Port 8080", "IN USE".to_string(), false));
                all_ok = false;
            }

            for (name, status, ok) in &checks {
                let status_str = if *ok {
                    status.green().bold()
                } else {
                    status.red().bold()
                };
                println!("{} {}: {}", "→".cyan(), name.bold(), status_str);
            }

            println!();
            if all_ok {
                println!("{}", "All checks passed!".green().bold());
                println!();
                println!("{} Run `oplire dashboard` to start the management interface", "Tip:".cyan());
            } else {
                println!("{}", "Some checks failed.".yellow().bold());
                println!();
                println!("{} Run `oplire setup` for guided installation", "Fix:".cyan());
            }
        }

        Commands::QuickReset {} => {
            if !warp_installed {
                println!("{} WARP no esta instalado", "[ERROR]".red());
                println!("{} Ejecute `oplire install warp` primero", "Consejo:".cyan().bold());
                return;
            }

            println!("{}", "Reset rapido del tunel WARP...".bold());

            if cli.verbose {
                eprintln!("{} Paso 1: Desconectando...", "[DEBUG]".cyan());
            }
            let _ = run_command("warp-cli", &["disconnect"], cli.dry_run, cli.verbose);

            std::thread::sleep(std::time::Duration::from_millis(1000 + (std::time::SystemTime::now().duration_since(std::time::UNIX_EPOCH).unwrap_or_default().subsec_nanos() as u64 % 500)));

            if cli.verbose {
                eprintln!("{} Paso 2: Eliminando registro anterior...", "[DEBUG]".cyan());
            }
            let _ = run_command(
                "warp-cli",
                &["registration", "delete"],
                cli.dry_run,
                cli.verbose,
            );

            std::thread::sleep(std::time::Duration::from_millis(500 + (std::time::SystemTime::now().duration_since(std::time::UNIX_EPOCH).unwrap_or_default().subsec_nanos() as u64 % 300)));

            if cli.verbose {
                eprintln!("{} Paso 3: Creando nuevo registro...", "[DEBUG]".cyan());
            }
            let _ = run_command(
                "warp-cli",
                &["registration", "new"],
                cli.dry_run,
                cli.verbose,
            );

            std::thread::sleep(std::time::Duration::from_millis(1000 + (std::time::SystemTime::now().duration_since(std::time::UNIX_EPOCH).unwrap_or_default().subsec_nanos() as u64 % 500)));

            if cli.verbose {
                eprintln!("{} Paso 4: Conectando...", "[DEBUG]".cyan());
            }
            let _ = run_command("warp-cli", &["connect"], cli.dry_run, cli.verbose);

            println!("{}", "Reset rapido completado!".green().bold());
        }

        Commands::Config { action } => match action {
            ConfigAction::Show {} => {
                let config = load_config();
                println!("{}", "Configuracion Actual:".bold());
                println!();
                println!("{} {}", "Escucha:".bold(), config.listen);
                println!("{} {}", "Upstream:".bold(), config.upstream);
                println!("{} {}", "Max. Reintentos:".bold(), config.max_retries);
                println!("{} {}ms", "Retraso WARP:".bold(), config.warp_delay);
                println!("{} {}", "Archivo config:".bold(), config_path().display());
            }
            ConfigAction::Set {
                key: _,
                listen,
                upstream,
                max_retries,
                warp_delay,
            } => {
                let mut config = load_config();

                config.listen = listen.clone();
                config.upstream = upstream.clone();
                config.max_retries = *max_retries;
                config.warp_delay = *warp_delay;

                match save_config(&config) {
                    Ok(()) => {
                        println!("{}", "Configuracion guardada!".green().bold());
                        println!("{} {}", "Archivo:".bold(), config_path().display());
                    }
                    Err(e) => {
                        eprintln!("{} Error al guardar config: {}", "[ERROR]".red(), e);
                        std::process::exit(1);
                    }
                }
            }
            ConfigAction::Reset {} => {
                let path = config_path();
                if path.exists() {
                    fs::remove_file(&path)
                        .map_err(|e| e.to_string())
                        .unwrap_or_else(|e| {
                            eprintln!("{} Error al eliminar config: {}", "[ERROR]".red(), e);
                            std::process::exit(1);
                        });
                    println!("{}", "Configuracion restaurada a valores por defecto!".green().bold());
                } else {
                    println!("{} No se encontro archivo de configuracion", "[INFO]".green());
                }
            }
        },

        Commands::Proxy {
            listen,
            upstream,
            api_key,
            max_retries,
            warp_delay,
        } => {
            let config = ProxyConfig {
                listen_addr: listen.clone(),
                opencode_base_url: upstream.clone(),
                opencode_api_key: api_key.clone(),
                max_retries: *max_retries,
                warp_reset_delay_ms: *warp_delay,
            };

            print_banner();
            println!("{}", "Proxy Anthropic <-> OpenCode Zen".bold().cyan());
            println!();
            println!("{} Escuchando en:    {}", "→".green(), listen.bold());
            println!("{} Upstream:          {}", "→".green(), upstream.bold());
            println!(
                "{} Max. reintentos:   {}",
                "→".green(),
                max_retries.to_string().bold()
            );
            println!();
            println!(
                "{} Configure Claude Code para usar: {}",
                "Consejo:".cyan().bold(),
                format!("http://{}", listen).yellow().bold()
            );
            println!("{} O ejecute: {}", "→".cyan(), "oplire connect claude-code".bold());
            println!();

            let rt = tokio::runtime::Runtime::new().unwrap();
            if let Err(e) = rt.block_on(async {
                oplire_reset::proxy::start_proxy_server(config).await
            }) {
                eprintln!("{} Proxy server error: {}", "[ERROR]".red(), e);
                std::process::exit(1);
            }
        }

        Commands::Status { json } => {
            if !warp_installed {
                if *json {
                    println!("{{\"connected\": false, \"tunnel_id\": null, \"error\": \"warp-cli not installed\"}}");
                } else {
                    println!("{} {}", "Tunel:".bold(), "No conectado".red());
                    println!("{} {}", "WARP:".bold(), "No instalado".red());
                    println!(
                        "\n{} Ejecute `oplire install warp` para instalar WARP",
                        "Consejo:".cyan().bold()
                    );
                }
                return;
            }

            println!("{}", "Verificando estado del tunel...".dimmed());

            match run_command("warp-cli", &["status"], cli.dry_run, cli.verbose) {
                Ok(output) => {
                    let status_str = output.trim();
                    let connected =
                        status_str.contains("Connected") || status_str.contains("connected");

                    if *json {
                        let tunnel_id = if connected { "active" } else { "null" };
                        println!(
                            "{{\"connected\": {}, \"tunnel_id\": \"{}\"}}",
                            connected, tunnel_id
                        );
                    } else {
                        if !status_str.is_empty() {
                            println!("{}", status_str);
                        }
                        let status = if connected {
                            "Active".green()
                        } else {
                            "Disconnected".red()
                        };
                        let tunnel = if connected {
                            "Connected".green()
                        } else {
                            "Not connected".red()
                        };
                        println!("\n{} {}", "Tunnel:".bold(), tunnel);
                        println!("{} {}", "WARP:".bold(), status);
                    }
                }
                Err(e) => {
                    if cli.verbose {
                        eprintln!("{} Error: {}", "[ERROR]".red(), e);
                    }
                    if *json {
                        println!(
                            "{{\"connected\": false, \"tunnel_id\": null, \"error\": \"{}\"}}",
                            e
                        );
                    } else {
                        println!("{} {}", "Tunnel:".bold(), "Error".red());
                        println!("{} {}", "Status:".bold(), e.red());
                    }
                }
            }
        }

        Commands::Reset {} => {
            if !warp_installed {
                println!("{} WARP no esta instalado", "[ERROR]".red());
                println!("{} Ejecute `oplire install warp` primero", "Consejo:".cyan().bold());
                return;
            }

            println!("{}", "Reseteando tunel WARP...".bold());

            if cli.verbose {
                eprintln!("{} Paso 1: Desconectando...", "[DEBUG]".cyan());
            }
            let _ = run_command("warp-cli", &["disconnect"], cli.dry_run, cli.verbose);

            if cfg!(target_os = "linux") {
                if cli.verbose {
                    eprintln!("{} Step 2: Stopping warp-svc...", "[DEBUG]".cyan());
                }
                let _ = run_sudo_command("systemctl stop warp-svc", cli.dry_run, cli.verbose);

                if cli.verbose {
                    eprintln!("{} Step 3: Clearing cache...", "[DEBUG]".cyan());
                }
                let _ = run_sudo_command(
                    "rm -rf /var/lib/cloudflare-warp/*",
                    cli.dry_run,
                    cli.verbose,
                );

                if cli.verbose {
                    eprintln!("{} Step 4: Starting warp-svc...", "[DEBUG]".cyan());
                }
                let _ = run_sudo_command("systemctl start warp-svc", cli.dry_run, cli.verbose);
            } else if cfg!(target_os = "windows") {
                if cli.verbose {
                    eprintln!("{} Step 2: Stopping WARP service...", "[DEBUG]".cyan());
                }
                let _ = run_command("net", &["stop", "CloudflareWARP"], cli.dry_run, cli.verbose);

                if cli.verbose {
                    eprintln!("{} Step 3: Clearing cache...", "[DEBUG]".cyan());
                }
                if let Ok(appdata) = std::env::var("PROGRAMDATA") {
                    let warp_dir = format!("{}\\Cloudflare\\WARP", appdata);
                    let _ = fs::remove_dir_all(&warp_dir);
                }

                if cli.verbose {
                    eprintln!("{} Step 4: Starting WARP service...", "[DEBUG]".cyan());
                }
                let _ = run_command("net", &["start", "CloudflareWARP"], cli.dry_run, cli.verbose);
            }

            if cli.verbose {
                eprintln!("{} Step 5: Deleting old registration...", "[DEBUG]".cyan());
            }
            let _ = run_command(
                "warp-cli",
                &["registration", "delete"],
                cli.dry_run,
                cli.verbose,
            );

            std::thread::sleep(std::time::Duration::from_millis(500));

            if cli.verbose {
                eprintln!("{} Step 6: Registering new tunnel...", "[DEBUG]".cyan());
            }
            let _ = run_command(
                "warp-cli",
                &["registration", "new"],
                cli.dry_run,
                cli.verbose,
            );

            if cli.verbose {
                eprintln!("{} Step 7: Connecting...", "[DEBUG]".cyan());
            }
            let _ = run_command("warp-cli", &["connect"], cli.dry_run, cli.verbose);

            println!("{}", "WARP tunnel reset complete!".green().bold());
            println!("{} Run `oplire status` to verify", "Tip:".cyan());
        }

        Commands::Stop {} => {
            if !warp_installed {
                println!("{} WARP no esta instalado", "[ERROR]".red());
                println!("{} Ejecute `oplire install warp` primero", "Consejo:".cyan().bold());
                return;
            }

            println!("{}", "Deteniendo tunel WARP...".bold());

            if cli.verbose {
                eprintln!("{} Paso 1: Desconectando...", "[DEBUG]".cyan());
            }
            let _ = run_command("warp-cli", &["disconnect"], cli.dry_run, cli.verbose);

            if cfg!(target_os = "linux") {
                if cli.verbose {
                    eprintln!("{} Step 2: Stopping warp-svc...", "[DEBUG]".cyan());
                }
                let _ = run_sudo_command("systemctl stop warp-svc", cli.dry_run, cli.verbose);

                if cli.verbose {
                    eprintln!("{} Step 3: Disabling warp-svc...", "[DEBUG]".cyan());
                }
                let _ = run_sudo_command("systemctl disable warp-svc", cli.dry_run, cli.verbose);
            } else if cfg!(target_os = "windows") {
                if cli.verbose {
                    eprintln!("{} Step 2: Stopping WARP service...", "[DEBUG]".cyan());
                }
                let _ = run_command("net", &["stop", "CloudflareWARP"], cli.dry_run, cli.verbose);
            }

            println!("{}", "WARP tunnel stopped!".green().bold());
            println!("{} Run `oplire reset` to restart", "Tip:".cyan());
        }

        Commands::FixSessions {} => {
            print_banner();
            println!("{}", "Reparar Sesiones Corruptas de OpenCode".bold().cyan());
            println!();

            let guard = oplire_reset::sessions::SessionGuard::new();

            let rt = tokio::runtime::Runtime::new().unwrap();
            rt.block_on(async {
                guard.init().await;

                println!("{} Scanning for corrupted sessions...", "→".cyan());
                let sessions = guard.scan_opencode_sessions().await;
                let total = sessions.len();
                let corrupted = sessions.iter().filter(|s| !s.is_valid).count();

                println!("  Total sessions: {}", total.to_string().bold());
                println!("  Corrupted: {}", if corrupted > 0 {
                    corrupted.to_string().red().bold()
                } else {
                    "0".green().bold()
                });
                println!();

                if corrupted == 0 {
                    println!("{}", "No corrupted sessions found!".green().bold());
                    return;
                }

                println!("{} Found {} corrupted sessions", "→".cyan(), corrupted.to_string().yellow().bold());
                for session in sessions.iter().filter(|s| !s.is_valid) {
                    println!("  - {} ({})", session.id.bold(), session.error_message.as_deref().unwrap_or("unknown"));
                }
                println!();

                print!("{} Fix all corrupted sessions? [Y/n]: ", "→".cyan());
                use std::io::{self, Write};
                io::stdout().flush().ok();
                let mut input = String::new();
                io::stdin().read_line(&mut input).ok();

                if input.trim().is_empty() || input.trim().eq_ignore_ascii_case("y") {
                    match guard.fix_corrupted_sessions().await {
                        Ok(fixed) => {
                            println!();
                            println!("{} Fixed {} corrupted sessions!", "✓".green().bold(), fixed.to_string().green().bold());
                        }
                        Err(e) => {
                            eprintln!("{} Failed to fix sessions: {}", "[ERROR]".red(), e);
                        }
                    }
                } else {
                    println!("{} Cancelled.", "[INFO]".yellow());
                }
            });
        }

        Commands::SessionsStatus {} => {
            print_banner();
            println!("{}", "Salud de Sesiones de OpenCode".bold().cyan());
            println!();

            let guard = oplire_reset::sessions::SessionGuard::new();

            let rt = tokio::runtime::Runtime::new().unwrap();
            rt.block_on(async {
                guard.init().await;
                let report = guard.get_health_report().await;

                let total = report["total_sessions"].as_u64().unwrap_or(0);
                let valid = report["valid_sessions"].as_u64().unwrap_or(0);
                let corrupted = report["corrupted_sessions"].as_u64().unwrap_or(0);
                let limit_reached = report["limit_reached_sessions"].as_u64().unwrap_or(0);
                let resumable = report["resumable_sessions"].as_u64().unwrap_or(0);
                let health = report["health_score"].as_u64().unwrap_or(100);
                let fixed_all_time = report["total_fixed_all_time"].as_u64().unwrap_or(0);

                println!("{} Total sessions:       {}", "→".cyan(), total.to_string().bold());
                println!("{} Valid sessions:       {}", "→".cyan(), valid.to_string().green().bold());
                println!("{} Corrupted:            {}", "→".cyan(), if corrupted > 0 {
                    corrupted.to_string().red().bold()
                } else {
                    "0".green().bold()
                });
                println!("{} Limit reached:        {}", "→".cyan(), if limit_reached > 0 {
                    limit_reached.to_string().yellow().bold()
                } else {
                    "0".green().bold()
                });
                println!("{} Resumable:            {}", "→".cyan(), resumable.to_string().cyan().bold());
                println!("{} Health score:         {}%", "→".cyan(), health.to_string().bold());
                println!("{} Total fixed (all):    {}", "→".cyan(), fixed_all_time.to_string().cyan().bold());
                println!();

                if let Some(limit_details) = report["limit_reached_details"].as_array() {
                    if !limit_details.is_empty() {
                        println!("{}", "Sessions with token limits reached:".bold().yellow());
                        for d in limit_details {
                            let id = d["id"].as_str().unwrap_or("?");
                            let folder = d["folder"].as_str().unwrap_or("unknown");
                            let reason = d["limit_reason"].as_str().unwrap_or("unknown");
                            let model = d["model"].as_str().unwrap_or("unknown");
                            let resumable = d["resumable"].as_bool().unwrap_or(false);
                            println!(
                                "  - {} [{}] folder={} model={} resumable={}",
                                id.bold(),
                                reason.dimmed(),
                                folder.dimmed(),
                                model.dimmed(),
                                if resumable { "yes".green().bold() } else { "no".red().bold() }
                            );
                        }
                        println!();
                        println!("{} These sessions are preserved and can be resumed when tokens become available.", "Info:".cyan());
                    }
                }

                if let Some(details) = report["corrupted_details"].as_array() {
                    if !details.is_empty() {
                        println!("{}", "Corrupted sessions:".bold());
                        for d in details {
                            let id = d["id"].as_str().unwrap_or("?");
                            let error = d["error"].as_str().unwrap_or("unknown");
                            let size = d["size"].as_u64().unwrap_or(0);
                            println!("  - {} ({} bytes): {}", id.bold(), size, error.dimmed());
                        }
                        println!();
                        println!("{} Run `oplire fix-sessions` to repair", "Tip:".cyan());
                    }
                }
            });
        }

        Commands::SessionsList {} => {
            print_banner();
            println!("{}", "Sesiones por Carpeta".bold().cyan());
            println!();

            let guard = oplire_reset::sessions::SessionGuard::new();

            let rt = tokio::runtime::Runtime::new().unwrap();
            rt.block_on(async {
                guard.init().await;
                let by_folder = guard.get_sessions_by_folder().await;

                if by_folder.is_empty() {
                    println!("{} No sessions found", "[INFO]".yellow());
                    return;
                }

                for (folder, sessions) in &by_folder {
                    let limit_count = sessions.iter().filter(|s| s.status == oplire_reset::sessions::SessionStatus::LimitReached).count();
                    let active_count = sessions.iter().filter(|s| s.status == oplire_reset::sessions::SessionStatus::Active).count();

                    println!(
                        "{} {} ({} sessions, {} active, {} limit_reached)",
                        "→".cyan(),
                        folder.bold(),
                        sessions.len().to_string().bold(),
                        active_count.to_string().green().bold(),
                        if limit_count > 0 { limit_count.to_string().yellow().bold() } else { "0".green().bold() }
                    );

                    for session in sessions {
                        let status_str = match session.status {
                            oplire_reset::sessions::SessionStatus::Active => "active".green().bold(),
                            oplire_reset::sessions::SessionStatus::LimitReached => "limit_reached".yellow().bold(),
                            oplire_reset::sessions::SessionStatus::Paused => "paused".dimmed(),
                            oplire_reset::sessions::SessionStatus::Resumable => "resumable".cyan().bold(),
                            oplire_reset::sessions::SessionStatus::Completed => "completed".dimmed(),
                        };

                        println!(
                            "    {} [{}] msgs={} size={}B",
                            session.id.bold(),
                            status_str,
                            session.message_count.to_string().dimmed(),
                            session.size_bytes.to_string().dimmed()
                        );
                    }
                    println!();
                }
            });
        }

        Commands::SessionDetail { id } => {
            print_banner();
            println!("{}", "Detalle de Sesion".bold().cyan());
            println!();

            let guard = oplire_reset::sessions::SessionGuard::new();

            let rt = tokio::runtime::Runtime::new().unwrap();
            rt.block_on(async {
                guard.init().await;

                let session_id = match id {
                    Some(id) => id,
                    None => {
                        println!("{} Please provide a session ID with --id <session_id>", "[INFO]".yellow());
                        println!("{} Use `oplire sessions-list` to see available sessions", "Tip:".cyan());
                        return;
                    }
                };

                match guard.find_session_by_id(&session_id).await {
                    Some(session) => {
                        println!("{} {}", "ID:".bold(), session.id.bold());
                        println!("{} {}", "Path:".bold(), session.path.dimmed());
                        println!("{} {}", "Folder:".bold(), session.folder.unwrap_or_else(|| "unknown".to_string()).dimmed());
                        println!("{} {:?}", "Status:".bold(), session.status);
                        println!("{} {}", "Valid:".bold(), if session.is_valid { "yes".green().bold() } else { "no".red().bold() });
                        println!("{} {}", "Resumable:".bold(), if session.resumable { "yes".green().bold() } else { "no".red().bold() });
                        println!("{} {}", "Messages:".bold(), session.message_count.to_string().bold());
                        println!("{} {} bytes", "Size:".bold(), session.size_bytes.to_string().bold());
                        println!("{} {}", "Model:".bold(), session.model.unwrap_or_else(|| "unknown".to_string()).dimmed());

                        if let Some(ref usage) = session.token_usage {
                            println!("{} input={}, output={}, total={}",
                                "Tokens:".bold(),
                                usage.input_tokens.to_string().yellow().bold(),
                                usage.output_tokens.to_string().yellow().bold(),
                                usage.total_tokens.to_string().yellow().bold()
                            );
                        }

                        if let Some(at) = session.limit_reached_at {
                            println!("{} {}", "Limit reached at:".bold(), at.to_string().yellow().bold());
                        }

                        if let Some(ref reason) = session.limit_reason {
                            println!("{} {}", "Limit reason:".bold(), reason.yellow().bold());
                        }

                        if let Some(ref err) = session.error_message {
                            println!("{} {}", "Error:".bold(), err.red().bold());
                        }

                        println!();
                        if session.status == oplire_reset::sessions::SessionStatus::LimitReached || session.resumable {
                            println!("{} This session can be resumed when tokens become available.", "Info:".cyan());
                            println!("{} The conversation history is fully preserved.", "Info:".cyan());
                        }
                    }
                    None => {
                        println!("{} Session '{}' not found", "[ERROR]".red(), session_id.bold());
                        println!("{} Use `oplire sessions-list` to see available sessions", "Tip:".cyan());
                    }
                }
            });
        }

        Commands::About {} => {
            print_banner();
            println!();
            println!("{} {}", "Version:".bold(), VERSION);
            println!("{} Rust", "Lenguaje:".bold());
            println!("{} Rotacion de IP + Proxy Profesional para OpenCode", "Proposito:".bold());
            println!("{} Cloudflare WARP + Axum HTTP", "Infraestructura:".bold());
            println!("{} Berke Oruc", "Autor:".bold());
            println!(
                "{} https://github.com/BerkeOruc/oplire",
                "GitHub:".bold()
            );
            println!();
            println!("{}", "Instalacion:".bold());
            println!("  oplire install warp          # Instalar Cloudflare WARP");
            println!("  oplire install opencode      # Instalar OpenCode");
            println!("  oplire install claude-code   # Instalar Claude Code CLI");
            println!("  oplire install all           # Instalar todo");
            println!("  oplire setup                 # Asistente de configuracion");
            println!();
            println!("{}", "Gestion WARP:".bold());
            println!("  oplire status              # Ver estado de WARP");
            println!("  oplire reset               # Reinicio completo del tunel WARP");
            println!("  oplire quick-reset         # Rotacion rapida de IP WARP");
            println!("  oplire stop                # Detener tunel WARP");
            println!();
            println!("{}", "Proxy y Claude Code:".bold());
            println!("  oplire proxy               # Iniciar proxy inverso");
            println!("  oplire connect claude-code # Proxy + lanzar Claude Code");
            println!("  oplire daemon              # Servicio proxy en segundo plano");
            println!("  oplire watch               # Monitorear OpenCode, auto-reset");
            println!();
            println!("{}", "Dashboard:".bold());
            println!("  oplire dashboard           # Iniciar proxy + panel web");
            println!();
            println!("{}", "Bypass de OpenCode Desktop:".bold());
            println!("  oplire setup-desktop       # Configurar Desktop para usar proxy");
            println!("  oplire restore-desktop     # Restaurar config original de Desktop");
            println!("  oplire desktop-status      # Ver estado del bypass");
            println!();
            println!("{}", "Gestion de Sesiones:".bold());
            println!("  oplire fix-sessions        # Reparar sesiones corruptas de OpenCode");
            println!("  oplire sessions-status     # Ver salud de sesiones");
            println!("  oplire sessions-list       # Listar sesiones por carpeta");
            println!("  oplire session-detail --id # Ver detalles de sesion");
            println!();
            println!("{}", "Configuracion:".bold());
            println!("  oplire models              # Listar modelos disponibles de OpenCode");
            println!("  oplire config show         # Ver config actual");
            println!("  oplire config set          # Guardar config");
            println!("  oplire config reset        # Restaurar valores por defecto");
            println!("  oplire doctor              # Diagnosticar configuracion del sistema");
        }
    }

    if !matches!(&cli.command, Commands::About {} | Commands::Proxy { .. } | Commands::Connect { .. } | Commands::Daemon { .. } | Commands::Watch { .. } | Commands::Doctor {} | Commands::Config { .. } | Commands::Setup {} | Commands::Install { .. } | Commands::Models { .. } | Commands::Dashboard { .. } | Commands::SetupDesktop { .. } | Commands::RestoreDesktop {} | Commands::DesktopStatus {}) {
        println!("\n{} v{}", "oplire".bold(), VERSION.dimmed());
    }
}
