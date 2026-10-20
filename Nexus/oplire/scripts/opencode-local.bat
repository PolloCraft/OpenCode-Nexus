@echo off
setlocal

set "SCRIPT_DIR=%~dp0"
set "SCRIPT_DIR=%SCRIPT_DIR:~0,-1%"

where opencode >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] opencode no encontrado en PATH
    pause
    exit /b 1
)

:LOCAL_MENU
cls
echo.
echo  ============================================
echo   OpenCode Local - Servidor Local
echo  ============================================
echo.
echo  URL:  http://127.0.0.1:3000
echo.
echo  [1] Iniciar servidor (puerto 3000)
echo  [2] Puerto personalizado
echo  [3] Abrir navegador
echo  [4] Verificar estado
echo  [0] Salir
echo.
echo  ============================================
echo.
set /p "LOPT=Selecciona: "

if "%LOPT%"=="1" goto LOCAL_RUN
if "%LOPT%"=="2" goto LOCAL_CUSTOM
if "%LOPT%"=="3" start http://127.0.0.1:3000 & goto LOCAL_MENU
if "%LOPT%"=="4" goto LOCAL_CHECK
if "%LOPT%"=="0" exit /b 0
echo Opcion invalida.
timeout /t 2 >nul
goto LOCAL_MENU

:LOCAL_RUN
cls
echo.
echo  Iniciando OpenCode Local en 127.0.0.1:3000...
echo  Presiona Ctrl+C para detener.
echo.
opencode serve --hostname 127.0.0.1 --port 3000
echo.
pause
goto LOCAL_MENU

:LOCAL_CUSTOM
set /p "CPORT=Puerto (default 3000): "
if "%CPORT%"=="" set "CPORT=3000"
echo.
echo  Iniciando en puerto %CPORT%...
echo  Presiona Ctrl+C para detener.
echo.
opencode serve --hostname 127.0.0.1 --port %CPORT%
echo.
pause
goto LOCAL_MENU

:LOCAL_CHECK
cls
echo.
echo  Verificando 127.0.0.1:3000...
powershell -Command "try { $r = Invoke-WebRequest -Uri 'http://127.0.0.1:3000' -TimeoutSec 3 -UseBasicParsing; Write-Host '[OK] Status:' $r.StatusCode } catch { Write-Host '[OFF] Servidor no disponible' }"
echo.
pause
goto LOCAL_MENU
