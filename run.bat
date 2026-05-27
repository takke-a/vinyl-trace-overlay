@echo off

:: Check Python
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo ERROR: Python not found. Install from https://python.org
    pause
    exit /b 1
)

:: Auto-install Pillow if missing
pip show Pillow >nul 2>&1
if %errorlevel% neq 0 (
    echo Installing Pillow...
    pip install Pillow
    if %errorlevel% neq 0 (
        echo ERROR: Failed to install Pillow.
        pause
        exit /b 1
    )
)

echo Starting Vinyl Trace Overlay...
python vinyl_trace_overlay.py
