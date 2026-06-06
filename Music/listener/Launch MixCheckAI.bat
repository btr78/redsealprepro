@echo off
TITLE MixCheck AI
SET PORT=8742
SET DIR=%~dp0

echo  _  _ _     ___ _           _       _   ___
echo ^| ^|| ^| ^|  __^| __^| ^|_  ___ __^| ^|__  /_\ ^|_ _^|
echo ^| ^|_^| ^| ^|_/ _^` ^| ' \/ -_) _^` ^| / // _ \ ^| ^|
echo  \___/^|____\__,^|_^|^|_\___\__,^|_\_\_/ \_\___^|
echo.
echo  Worship Audio Analyzer
echo  ========================
echo.

:: Check Python is installed
python --version >nul 2>&1
IF ERRORLEVEL 1 (
  echo [ERROR] Python 3 is not installed.
  echo.
  echo  Please install it from https://www.python.org/downloads/
  echo  Make sure to check "Add Python to PATH" during install.
  echo.
  pause
  exit /b 1
)

:: Kill anything already on our port
FOR /F "tokens=5" %%a IN ('netstat -aon 2^>nul ^| findstr /R ":%PORT% "') DO (
  taskkill /F /PID %%a >nul 2>&1
)

:: Start the proxy server in background
cd /d "%DIR%"
start /B python server.py

:: Wait for server to be ready (up to 5 seconds)
SET /A tries=0
:waitloop
timeout /t 1 /nobreak >nul
curl -sf http://127.0.0.1:%PORT%/index.html >nul 2>&1
IF NOT ERRORLEVEL 1 GOTO ready
SET /A tries+=1
IF %tries% LSS 5 GOTO waitloop

:ready
:: Open in default browser
start http://127.0.0.1:%PORT%/index.html

echo  [OK] MixCheck AI is running at http://127.0.0.1:%PORT%
echo.
echo  Keep this window open while using the app.
echo  Press Ctrl+C to stop the server.
echo.
pause > nul
