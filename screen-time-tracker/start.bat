@echo off
title Screen Time Tracker — Launcher
color 0A

echo.
echo  ====================================
echo   SCREEN TIME TRACKER
echo  ====================================
echo.

:: Check Python is installed
python --version >nul 2>&1
if errorlevel 1 (
    echo  ERROR: Python not found.
    echo  Download it from https://www.python.org/downloads/
    echo  Make sure to check "Add Python to PATH" during install.
    echo.
    pause
    exit /b 1
)

echo  Python found. Checking setup...
echo.

:: ── Backend setup ──────────────────────────────────────
if not exist "%~dp0backend\venv\Scripts\activate.bat" (
    echo  [1/4] Creating backend virtual environment...
    cd /d "%~dp0backend"
    python -m venv venv
    if errorlevel 1 (
        echo  ERROR: Failed to create backend venv.
        pause
        exit /b 1
    )
    echo  [2/4] Installing backend packages (this takes ~30 seconds)...
    call venv\Scripts\activate.bat
    pip install -r requirements.txt --quiet
    if errorlevel 1 (
        echo  ERROR: pip install failed for backend.
        pause
        exit /b 1
    )
    echo  Backend ready.
) else (
    echo  Backend already set up. Skipping install.
)

:: ── Agent setup ────────────────────────────────────────
if not exist "%~dp0agent\venv\Scripts\activate.bat" (
    echo  [3/4] Creating agent virtual environment...
    cd /d "%~dp0agent"
    python -m venv venv
    if errorlevel 1 (
        echo  ERROR: Failed to create agent venv.
        pause
        exit /b 1
    )
    echo  [4/4] Installing agent packages...
    call venv\Scripts\activate.bat
    pip install -r requirements.txt --quiet
    if errorlevel 1 (
        echo  ERROR: pip install failed for agent.
        pause
        exit /b 1
    )
    echo  Agent ready.
) else (
    echo  Agent already set up. Skipping install.
)

:: ── Copy env files if missing ───────────────────────────
if not exist "%~dp0backend\.env" (
    copy "%~dp0backend\.env.example" "%~dp0backend\.env" >nul
)
if not exist "%~dp0agent\.env" (
    copy "%~dp0agent\.env.example" "%~dp0agent\.env" >nul
)

:: ── Launch ──────────────────────────────────────────────
echo.
echo  Starting backend...
start "Screen Time — Backend" cmd /k "title Screen Time Backend && cd /d %~dp0 && call backend\venv\Scripts\activate.bat && python -m uvicorn backend.main:app --reload && pause"

echo  Waiting for backend to start...
timeout /t 4 /nobreak >nul

echo  Starting agent...
start "Screen Time — Agent" cmd /k "title Screen Time Agent && cd /d %~dp0agent && call venv\Scripts\activate.bat && python tracker.py && pause"

echo  Opening dashboard...
timeout /t 2 /nobreak >nul
start "" "%~dp0frontend\dashboard.html"

echo.
echo  ====================================
echo   All services launched!
echo.
echo   Dashboard opened in your browser.
echo   Keep this window open — close it
echo   to stop everything.
echo  ====================================
echo.
echo  Press any key to close this launcher.
pause >nul
