@echo off
echo ============================================
echo  Vinyl Trace Overlay - Build EXE
echo ============================================

:: Check Python
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo ERROR: Python not found.
    echo Install from https://python.org and add to PATH.
    pause
    exit /b 1
)

:: Install / upgrade PyInstaller
pip show pyinstaller >nul 2>&1
if %errorlevel% neq 0 (
    echo Installing PyInstaller...
    pip install pyinstaller
)

:: Install Pillow if missing
pip show Pillow >nul 2>&1
if %errorlevel% neq 0 (
    pip install Pillow
)

:: Clean old build artifacts
if exist build  rmdir /s /q build
if exist dist   rmdir /s /q dist
if exist VinylTraceOverlay.spec del /q VinylTraceOverlay.spec

echo.
echo Building... (this may take 1-2 minutes)
echo.

pyinstaller ^
    --onefile ^
    --noconsole ^
    --name "VinylTraceOverlay" ^
    --collect-all PIL ^
    --hidden-import PIL ^
    --hidden-import PIL.Image ^
    --hidden-import PIL.ImageTk ^
    --hidden-import PIL.ImageFilter ^
    --hidden-import PIL.ImageOps ^
    --hidden-import PIL.ImageEnhance ^
    --hidden-import PIL.ImageDraw ^
    vinyl_trace_overlay.py

echo.
if exist "dist\VinylTraceOverlay.exe" (
    echo ============================================
    echo  Build successful!
    echo  Output: dist\VinylTraceOverlay.exe
    echo ============================================
    explorer dist
) else (
    echo ============================================
    echo  Build FAILED.
    echo  Check the output above for error details.
    echo  Common fixes:
    echo    - Run as Administrator
    echo    - Disable antivirus temporarily
    echo    - pip install --upgrade pyinstaller
    echo ============================================
)

pause
