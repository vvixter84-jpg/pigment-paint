@echo off
setlocal
cd /d "%~dp0"
set "PYTHONUTF8=1"

if exist ".venv\Scripts\python.exe" (
    ".venv\Scripts\python.exe" -c "import PyQt6" >nul 2>nul
    if errorlevel 1 (
        echo Recreating the virtual environment...
        rmdir /s /q ".venv"
    )
)

if not exist ".venv\Scripts\pythonw.exe" (
    call setup.bat
    if errorlevel 1 (
        echo.
        echo Environment setup failed.
        pause
        exit /b 1
    )
)

start "" ".venv\Scripts\pythonw.exe" "main.py"
