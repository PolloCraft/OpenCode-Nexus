@echo off
chcp 65001 >nul 2>&1
title NEXUS Suite
cd /d "%~dp0"

rem 1) Preferir el ejecutable compilado (no requiere Python)
if exist "Nexus.exe" (
    start "" "Nexus.exe"
    exit /b
)

rem 2) Si no hay .exe, ejecutar la GUI con Python
cd /d "%~dp0Nexus"
where pythonw >nul 2>nul
if %errorlevel%==0 (
    start "" pythonw nexus_app.py
    exit /b
)
where python >nul 2>nul
if %errorlevel%==0 (
    python nexus_app.py
    exit /b
)

echo [ERROR] No se encontro Nexus.exe ni Python.
echo         Instala Python desde https://www.python.org/downloads/
echo         (marca "Add Python to PATH" durante la instalacion).
pause
