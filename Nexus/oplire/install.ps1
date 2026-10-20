# oplire-installer.ps1 - Windows Installer for oplire
# Installs oplire to Program Files and adds to PATH

param(
    [switch]$Uninstall,
    [switch]$Force
)

$ErrorActionPreference = "Stop"
$AppName = "oplire"
$AppVersion = "3.0.0"
$Publisher = "Berke Oruc"

# Check admin rights
$isAdmin = ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)

function Write-Header {
    Write-Host ""
    Write-Host "====================================" -ForegroundColor Cyan
    Write-Host "   oplire Installer v$AppVersion" -ForegroundColor Cyan
    Write-Host "   OpenCode Rate Limit Reset" -ForegroundColor Cyan
    Write-Host "   by $Publisher" -ForegroundColor Cyan
    Write-Host "====================================" -ForegroundColor Cyan
    Write-Host ""
}

function Install-Application {
    if (-not $isAdmin) {
        Write-Host "[ERROR] This installer requires administrator privileges." -ForegroundColor Red
        Write-Host "Please run PowerShell as Administrator." -ForegroundColor Yellow
        exit 1
    }

    Write-Host "[INFO] Installing $AppName v$AppVersion..." -ForegroundColor Cyan
    Write-Host ""

    # Determine install directory
    $InstallDir = "$env:ProgramFiles\$AppName"
    $ExeSource = Join-Path $PSScriptRoot "oplire.exe"

    # Check if executable exists
    if (-not (Test-Path $ExeSource)) {
        # Try to find in target/release
        $ExeSource = Join-Path $PSScriptRoot "target\release\oplire.exe"
        if (-not (Test-Path $ExeSource)) {
            Write-Host "[ERROR] oplire.exe not found!" -ForegroundColor Red
            Write-Host "Please build the project first:" -ForegroundColor Yellow
            Write-Host "  .\build.ps1 -Release -Package" -ForegroundColor White
            exit 1
        }
    }

    # Create install directory
    Write-Host "[1/4] Creating installation directory..." -ForegroundColor Cyan
    if (-not (Test-Path $InstallDir)) {
        New-Item -ItemType Directory -Path $InstallDir -Force | Out-Null
    }

    # Copy executable
    Write-Host "[2/4] Installing executable..." -ForegroundColor Cyan
    Copy-Item $ExeSource -Destination "$InstallDir\oplire.exe" -Force

    # Create batch launchers
    $LauncherContent = @"
@echo off
"%~dp0oplire.exe" %*
"@
    Set-Content -Path "$InstallDir\oplire.bat" -Value $LauncherContent

    $DashboardLauncher = @"
@echo off
"%~dp0oplire.exe" dashboard %*
"@
    Set-Content -Path "$InstallDir\oplire-dashboard.bat" -Value $DashboardLauncher

    # Add to PATH
    Write-Host "[3/4] Adding to PATH..." -ForegroundColor Cyan
    $CurrentPath = [Environment]::GetEnvironmentVariable("Path", "Machine")
    if ($CurrentPath -notlike "*$InstallDir*") {
        [Environment]::SetEnvironmentVariable("Path", "$CurrentPath;$InstallDir", "Machine")
        Write-Host "  Added $InstallDir to system PATH" -ForegroundColor Green
    } else {
        Write-Host "  Already in PATH" -ForegroundColor Yellow
    }

    # Create Start Menu shortcuts
    Write-Host "[4/4] Creating Start Menu shortcuts..." -ForegroundColor Cyan
    $StartMenu = "$env:ProgramData\Microsoft\Windows\Start Menu\Programs"
    $ShortcutDir = Join-Path $StartMenu $AppName

    if (-not (Test-Path $ShortcutDir)) {
        New-Item -ItemType Directory -Path $ShortcutDir -Force | Out-Null
    }

    # Create shortcut for main executable
    $WScriptShell = New-Object -ComObject WScript.Shell

    $Shortcut = $WScriptShell.CreateShortcut("$ShortcutDir\oplire.lnk")
    $Shortcut.TargetPath = "$InstallDir\oplire.exe"
    $Shortcut.Arguments = "dashboard"
    $Shortcut.WorkingDirectory = $InstallDir
    $Shortcut.Description = "oplire - OpenCode Rate Limit Reset"
    $Shortcut.Save()

    $Shortcut = $WScriptShell.CreateShortcut("$ShortcutDir\oplire Dashboard.lnk")
    $Shortcut.TargetPath = "$InstallDir\oplire-dashboard.bat"
    $Shortcut.WorkingDirectory = $InstallDir
    $Shortcut.Description = "Open oplire Dashboard"
    $Shortcut.Save()

    $Shortcut = $WScriptShell.CreateShortcut("$ShortcutDir\oplire CLI.lnk")
    $Shortcut.TargetPath = "$InstallDir\oplire.exe"
    $Shortcut.WorkingDirectory = $InstallDir
    $Shortcut.Description = "oplire Command Line"
    $Shortcut.Save()

    Write-Host ""
    Write-Host "====================================" -ForegroundColor Green
    Write-Host "   Installation Complete!" -ForegroundColor Green
    Write-Host "====================================" -ForegroundColor Green
    Write-Host ""
    Write-Host "Installed to: $InstallDir" -ForegroundColor Yellow
    Write-Host ""
    Write-Host "Quick Start:" -ForegroundColor Cyan
    Write-Host "  1. Open Command Prompt or PowerShell" -ForegroundColor White
    Write-Host "  2. Run: oplire dashboard" -ForegroundColor White
    Write-Host "  3. Open http://127.0.0.1:8080 in your browser" -ForegroundColor White
    Write-Host ""
    Write-Host "Commands:" -ForegroundColor Cyan
    Write-Host "  oplire dashboard      # Start with web dashboard" -ForegroundColor White
    Write-Host "  oplire proxy          # Start proxy only" -ForegroundColor White
    Write-Host "  oplire doctor         # Run diagnostics" -ForegroundColor White
    Write-Host "  oplire setup          # Guided setup" -ForegroundColor White
    Write-Host ""
    Write-Host "Note: You may need to restart your terminal for PATH changes to take effect." -ForegroundColor Yellow
    Write-Host ""
}

function Uninstall-Application {
    if (-not $isAdmin) {
        Write-Host "[ERROR] Uninstaller requires administrator privileges." -ForegroundColor Red
        exit 1
    }

    Write-Host "[INFO] Uninstalling $AppName..." -ForegroundColor Cyan
    Write-Host ""

    $InstallDir = "$env:ProgramFiles\$AppName"

    # Remove from PATH
    Write-Host "[1/3] Removing from PATH..." -ForegroundColor Cyan
    $CurrentPath = [Environment]::GetEnvironmentVariable("Path", "Machine")
    $NewPath = ($CurrentPath -split ";" | Where-Object { $_ -ne $InstallDir }) -join ";"
    [Environment]::SetEnvironmentVariable("Path", $NewPath, "Machine")

    # Remove Start Menu shortcuts
    Write-Host "[2/3] Removing Start Menu shortcuts..." -ForegroundColor Cyan
    $StartMenu = "$env:ProgramData\Microsoft\Windows\Start Menu\Programs"
    $ShortcutDir = Join-Path $StartMenu $AppName
    if (Test-Path $ShortcutDir) {
        Remove-Item -Recurse -Force $ShortcutDir
    }

    # Remove installation directory
    Write-Host "[3/3] Removing installation files..." -ForegroundColor Cyan
    if (Test-Path $InstallDir) {
        Remove-Item -Recurse -Force $InstallDir
    }

    Write-Host ""
    Write-Host "====================================" -ForegroundColor Green
    Write-Host "   Uninstall Complete!" -ForegroundColor Green
    Write-Host "====================================" -ForegroundColor Green
    Write-Host ""
    Write-Host "$AppName has been removed from your system." -ForegroundColor Yellow
    Write-Host ""
}

# Main
Write-Header

if ($Uninstall) {
    Uninstall-Application
} else {
    Install-Application
}
