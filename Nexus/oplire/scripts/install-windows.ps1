# oplire-reset Windows Installer
# Installs Cloudflare WARP on Windows

param(
    [switch]$Force,
    [switch]$Verbose
)

$ErrorActionPreference = "Stop"

if ($Verbose) {
    Write-Host "[VERBOSE] Installation started" -ForegroundColor Cyan
}

# Check for admin rights
$isAdmin = ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)

if (-not $isAdmin) {
    Write-Host "Please run as Administrator" -ForegroundColor Red
    exit 1
}

# Check if WARP installed
$warpPath = "${env:ProgramFiles(x86)}\Cloudflare\Cloudflare WARP.exe"
$warpPathAlt = "${env:ProgramFiles}\Cloudflare\Cloudflare WARP.exe"

if ((Test-Path $warpPath) -or (Test-Path $warpPathAlt)) {
    if ($Force) {
        Write-Host "Reinstalling Cloudflare WARP..." -ForegroundColor Yellow
    } else {
        Write-Host "Cloudflare WARP is already installed" -ForegroundColor Green
        Write-Host "Use -Force to reinstall" -ForegroundColor Cyan
        exit 0
    }
}

Write-Host "Installing Cloudflare WARP..." -ForegroundColor Green

$installerUrl = "https://1111-releases.cloudflare.com/latest/Windows%20Cloudflare%20WARP%20Setup.exe"
$installerPath = "$env:TEMP\Cloudflare-WARP-Setup.exe"

try {
    Write-Host "Downloading installer..." -ForegroundColor Cyan
    Invoke-WebRequest -Uri $installerUrl -OutFile $installerPath -UseBasicParsing
    
    Write-Host "Running installer..." -ForegroundColor Cyan
    Start-Process -FilePath $installerPath -ArgumentList "/quiet /install" -Wait
    
    Remove-Item $installerPath -Force -ErrorAction SilentlyContinue
    
    Write-Host "Cloudflare WARP installed successfully!" -ForegroundColor Green
    Write-Host ""
    Write-Host "To connect, run:" -ForegroundColor White
    Write-Host '  & "C:\Program Files (x86)\Cloudflare\Cloudflare WARP.exe" connect' -ForegroundColor Cyan
    
} catch {
    Write-Host "Installation failed: $_" -ForegroundColor Red
    exit 1
}