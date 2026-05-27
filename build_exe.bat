@echo off
pip install pillow pyinstaller >nul 2>&1
pyinstaller --onefile --noconsole --name VinylTraceOverlay vinyl_trace_overlay.py
if exist dist\VinylTraceOverlay.exe (
    copy /y dist\VinylTraceOverlay.exe VinylTraceOverlay.exe
    rmdir /s /q dist
    rmdir /s /q build
    del /q VinylTraceOverlay.spec
    echo Done.
) else (
    echo Build failed.
)
pause
