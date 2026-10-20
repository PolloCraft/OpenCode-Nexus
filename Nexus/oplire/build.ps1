# oplire-build.ps1 - Build script for oplire Windows
# Creates a standalone .exe package

param(
    [switch]$Release,
    [switch]$Package,
    [switch]$Clean
)

$ErrorActionPreference = "Stop"
$ProjectRoot = $PSScriptRoot
$BuildDir = Join-Path $ProjectRoot "target"
$ReleaseDir = Join-Path $BuildDir "release"
$PackageDir = Join-Path $ProjectRoot "dist"

Write-Host "====================================" -ForegroundColor Cyan
Write-Host "   oplire Build Script" -ForegroundColor Cyan
Write-Host "   Windows x64" -ForegroundColor Cyan
Write-Host "====================================" -ForegroundColor Cyan
Write-Host ""

# Clean if requested
if ($Clean) {
    Write-Host "[CLEAN] Removing build artifacts..." -ForegroundColor Yellow
    if (Test-Path $BuildDir) {
        Remove-Item -Recurse -Force $BuildDir
    }
    Write-Host "[CLEAN] Done" -ForegroundColor Green
}

# Check Rust installation
Write-Host "[CHECK] Verifying Rust installation..." -ForegroundColor Cyan
try {
    $rustVersion = & rustc --version 2>&1
    Write-Host "  Rust: $rustVersion" -ForegroundColor Green
} catch {
    Write-Host "  Rust not found!" -ForegroundColor Red
    Write-Host "  Install from: https://rustup.rs/" -ForegroundColor Yellow
    exit 1
}

# Build
Write-Host ""
Write-Host "[BUILD] Compiling oplire..." -ForegroundColor Cyan

$cargoArgs = @("build")
if ($Release) {
    $cargoArgs += "--release"
}

Push-Location $ProjectRoot
try {
    & cargo @cargoArgs
    if ($LASTEXITCODE -ne 0) {
        throw "Build failed"
    }
} finally {
    Pop-Location
}

$ExeName = "oplire.exe"
$ExePath = if ($Release) {
    Join-Path $ReleaseDir $ExeName
} else {
    Join-Path $BuildDir "debug" $ExeName
}

if (-not (Test-Path $ExePath)) {
    Write-Host "[ERROR] Executable not found at: $ExePath" -ForegroundColor Red
    exit 1
}

$ExeSize = (Get-Item $ExePath).Length / 1MB
Write-Host "[BUILD] Compiled: $ExePath" -ForegroundColor Green
Write-Host "[BUILD] Size: $([math]::Round($ExeSize, 2)) MB" -ForegroundColor Green

# Package
if ($Package) {
    Write-Host ""
    Write-Host "[PACKAGE] Creating distribution package..." -ForegroundColor Cyan

    if (-not (Test-Path $PackageDir)) {
        New-Item -ItemType Directory -Path $PackageDir -Force | Out-Null
    }

    $PackageVersion = "3.0.0"
    $PackageName = "oplire-$PackageVersion-windows-x64"
    $PackagePath = Join-Path $PackageDir $PackageName

    if (Test-Path $PackagePath) {
        Remove-Item -Recurse -Force $PackagePath
    }
    New-Item -ItemType Directory -Path $PackagePath -Force | Out-Null

    # Copy executable
    Copy-Item $ExePath -Destination $PackagePath

    # Create batch launcher
    $LauncherContent = @"
@echo off
echo ====================================
echo    oplire - OpenCode Rate Limit Reset
echo    by Berke Oruc
echo ====================================
echo.
echo Starting oplire...
echo.
"%~dp0oplire.exe" %*
pause
"@
    Set-Content -Path (Join-Path $PackagePath "oplire.bat") -Value $LauncherContent

    # Create dashboard launcher
    $DashboardLauncher = @"
@echo off
echo ====================================
echo    oplire Dashboard
echo ====================================
echo.
echo Starting dashboard on http://127.0.0.1:8080
echo.
echo Open your browser to: http://127.0.0.1:8080
echo.
echo Press Ctrl+C to stop
echo.
"%~dp0oplire.exe" dashboard
pause
"@
    Set-Content -Path (Join-Path $PackagePath "oplire-dashboard.bat") -Value $DashboardLauncher

    # Create README
    $ReadmeContent = @"
oplire - OpenCode Rate Limit Reset
===================================

Version: $PackageVersion
Platform: Windows x64
Author: Berke Oruc

Quick Start
-----------
1. Double-click oplire-dashboard.bat to start the dashboard
2. Open http://127.0.0.1:8080 in your browser
3. Use the dashboard to manage settings

Command Line Usage
------------------
# Start proxy with dashboard
oplire.exe dashboard

# Start proxy only
oplire.exe proxy

# Check WARP status
oplire.exe status

# Reset WARP IP
oplire.exe reset

# Quick IP rotation
oplire.exe quick-reset

# Install components
oplire.exe setup

# Run diagnostics
oplire.exe doctor

# Connect Claude Code
oplire.exe connect claude-code

OpenCode Desktop Integration
-----------------------------
To use with OpenCode Desktop:

1. Start the proxy:
   oplire.exe proxy

2. Configure OpenCode Desktop to use:
   - API Base URL: http://127.0.0.1:8080
   - API Key: oplire-proxy-key

3. Or use environment variables:
   set ANTHROPIC_BASE_URL=http://127.0.0.1:8080
   set ANTHROPIC_API_KEY=oplire-proxy-key

Available Free Models
---------------------
- GLM 4.7 Free (glm-4.7-free)
- MiniMax M2.1 Free (minimax-m2.1-free)
- Kimi K2.5 Free (kimi-k2.5-free)
- Qwen 2.5 72B Free (qwen-2.5-72b-free)
- Llama 3.3 70B Free (llama-3.3-70b-free)

Links
-----
GitHub: https://github.com/BerkeOruc/oplire
Issues: https://github.com/BerkeOruc/oplire/issues

License
-------
MIT License
"@
    Set-Content -Path (Join-Path $PackagePath "README.txt") -Value $ReadmeContent

    # Create zip
    $ZipPath = Join-Path $PackageDir "$PackageName.zip"
    if (Test-Path $ZipPath) {
        Remove-Item $ZipPath -Force
    }
    Compress-Archive -Path $PackagePath -DestinationPath $ZipPath

    Write-Host "[PACKAGE] Created: $ZipPath" -ForegroundColor Green
    Write-Host "[PACKAGE] Contents:" -ForegroundColor Cyan
    Get-ChildItem $PackagePath | ForEach-Object {
        Write-Host "  - $($_.Name)" -ForegroundColor White
    }

    # Cleanup temp directory
    Remove-Item -Recurse -Force $PackagePath
}

Write-Host ""
Write-Host "====================================" -ForegroundColor Green
Write-Host "   Build Complete!" -ForegroundColor Green
Write-Host "====================================" -ForegroundColor Green
Write-Host ""
Write-Host "Executable: $ExePath" -ForegroundColor Yellow
if ($Package) {
    Write-Host "Package: $ZipPath" -ForegroundColor Yellow
}
Write-Host ""
Write-Host "Usage:" -ForegroundColor Cyan
Write-Host "  oplire.exe dashboard    # Start with web dashboard" -ForegroundColor White
Write-Host "  oplire.exe proxy        # Start proxy only" -ForegroundColor White
Write-Host "  oplire.exe doctor       # Run diagnostics" -ForegroundColor White
Write-Host ""
