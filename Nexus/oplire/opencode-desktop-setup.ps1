# opencode-desktop-setup.ps1 - Setup OpenCode Desktop to use oplire proxy
# Configures the desktop application to route through oplire

param(
    [switch]$Restore,
    [switch]$Status
)

$ErrorActionPreference = "Stop"

# OpenCode Desktop paths
$OpenCodePaths = @(
    "$env:APPDATA\opencode",
    "$env:LOCALAPPDATA\opencode",
    "$env:USERPROFILE\.opencode"
)

$ConfigFile = "config.json"
$ProxyConfig = @{
    ApiBaseUrl = "http://127.0.0.1:8080"
    ApiKey = "oplire-proxy-key"
}

function Write-Header {
    Write-Host ""
    Write-Host "====================================" -ForegroundColor Cyan
    Write-Host "   OpenCode Desktop Setup" -ForegroundColor Cyan
    Write-Host "   Configure with oplire proxy" -ForegroundColor Cyan
    Write-Host "====================================" -ForegroundColor Cyan
    Write-Host ""
}

function Find-OpenCodeConfig {
    foreach ($Path in $OpenCodePaths) {
        $ConfigPath = Join-Path $Path $ConfigFile
        if (Test-Path $ConfigPath) {
            return $ConfigPath
        }
    }
    return $null
}

function Backup-Config {
    param($ConfigPath)
    
    $BackupPath = "$ConfigPath.bak.$(Get-Date -Format 'yyyyMMdd-HHmmss')"
    Copy-Item $ConfigPath $BackupPath
    Write-Host "  Backed up: $BackupPath" -ForegroundColor Green
    return $BackupPath
}

function Set-ProxyConfig {
    param($ConfigPath)
    
    $Config = @{}
    if (Test-Path $ConfigPath) {
        $Config = Get-Content $ConfigPath | ConvertFrom-Json -AsHashtable
    }
    
    # Add or update proxy settings
    if (-not $Config.ContainsKey("api")) {
        $Config["api"] = @{}
    }
    
    $Config["api"]["base_url"] = $ProxyConfig.ApiBaseUrl
    $Config["api"]["key"] = $ProxyConfig.ApiKey
    
    # Save config
    $Config | ConvertTo-Json -Depth 10 | Set-Content $ConfigPath
    Write-Host "  Updated: $ConfigPath" -ForegroundColor Green
}

function Get-Status {
    Write-Host ""
    Write-Host "OpenCode Desktop Configuration Status" -ForegroundColor Cyan
    Write-Host "-------------------------------------" -ForegroundColor Cyan
    Write-Host ""
    
    $ConfigPath = Find-OpenCodeConfig
    
    if ($ConfigPath) {
        Write-Host "Config file: $ConfigPath" -ForegroundColor Green
        
        $Config = Get-Content $ConfigPath | ConvertFrom-Json
        
        if ($Config.api -and $Config.api.base_url) {
            Write-Host "API Base URL: $($Config.api.base_url)" -ForegroundColor White
            Write-Host "API Key: $($Config.api.key)" -ForegroundColor White
            
            if ($Config.api.base_url -eq $ProxyConfig.ApiBaseUrl) {
                Write-Host ""
                Write-Host "Status: Configured for oplire proxy" -ForegroundColor Green
            } else {
                Write-Host ""
                Write-Host "Status: NOT configured for oplire proxy" -ForegroundColor Yellow
            }
        } else {
            Write-Host ""
            Write-Host "Status: No API configuration found" -ForegroundColor Yellow
        }
    } else {
        Write-Host "Config file: Not found" -ForegroundColor Red
        Write-Host ""
        Write-Host "OpenCode Desktop may not be installed." -ForegroundColor Yellow
    }
    
    Write-Host ""
}

function Restore-OriginalConfig {
    param($ConfigPath)
    
    $LatestBackup = Get-ChildItem "$ConfigPath.bak.*" | 
        Sort-Object LastWriteTime -Descending | 
        Select-Object -First 1
    
    if ($LatestBackup) {
        Copy-Item $LatestBackup.FullName $ConfigPath -Force
        Write-Host "  Restored from: $($LatestBackup.Name)" -ForegroundColor Green
    } else {
        Write-Host "  No backup found" -ForegroundColor Yellow
    }
}

# Main
Write-Header

if ($Status) {
    Get-Status
    exit 0
}

$ConfigPath = Find-OpenCodeConfig

if (-not $ConfigPath) {
    Write-Host "[INFO] OpenCode Desktop config not found." -ForegroundColor Yellow
    Write-Host ""
    Write-Host "This script configures OpenCode Desktop to use oplire proxy." -ForegroundColor Cyan
    Write-Host ""
    Write-Host "Make sure OpenCode Desktop is installed and has been run at least once." -ForegroundColor Yellow
    Write-Host ""
    
    # Create config directory if it doesn't exist
    $ConfigDir = $OpenCodePaths[0]
    if (-not (Test-Path $ConfigDir)) {
        New-Item -ItemType Directory -Path $ConfigDir -Force | Out-Null
    }
    
    $ConfigPath = Join-Path $ConfigDir $ConfigFile
    Write-Host "Creating new config at: $ConfigPath" -ForegroundColor Cyan
}

if ($Restore) {
    Write-Host "[RESTORE] Restoring original configuration..." -ForegroundColor Cyan
    Restore-OriginalConfig $ConfigPath
    Write-Host ""
    Write-Host "Original configuration restored!" -ForegroundColor Green
} else {
    Write-Host "[SETUP] Configuring OpenCode Desktop..." -ForegroundColor Cyan
    Write-Host ""
    
    # Backup existing config
    if (Test-Path $ConfigPath) {
        Write-Host "[BACKUP] Creating backup..." -ForegroundColor Cyan
        Backup-Config $ConfigPath
    }
    
    # Set proxy configuration
    Write-Host "[CONFIG] Setting proxy configuration..." -ForegroundColor Cyan
    Set-ProxyConfig $ConfigPath
    
    Write-Host ""
    Write-Host "====================================" -ForegroundColor Green
    Write-Host "   Setup Complete!" -ForegroundColor Green
    Write-Host "====================================" -ForegroundColor Green
    Write-Host ""
    Write-Host "OpenCode Desktop is now configured to use oplire proxy." -ForegroundColor Green
    Write-Host ""
    Write-Host "Next Steps:" -ForegroundColor Cyan
    Write-Host "  1. Start oplire: oplire dashboard" -ForegroundColor White
    Write-Host "  2. Open OpenCode Desktop" -ForegroundColor White
    Write-Host "  3. The desktop app will now use oplire proxy" -ForegroundColor White
    Write-Host ""
    Write-Host "The proxy will automatically:" -ForegroundColor Cyan
    Write-Host "  - Translate API requests" -ForegroundColor White
    Write-Host "  - Handle rate limits" -ForegroundColor White
    Write-Host "  - Reset WARP IP when needed" -ForegroundColor White
    Write-Host ""
    Write-Host "To restore original config: .\opencode-desktop-setup.ps1 -Restore" -ForegroundColor Yellow
    Write-Host ""
}
