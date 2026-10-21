@echo off
setlocal
cd /d "%~dp0"
set "PYTHONUTF8=1"

if not exist ".venv\Scripts\python.exe" (
    call setup.bat
    if errorlevel 1 (
        pause
        exit /b 1
    )
)

echo Installing PyInstaller...
".venv\Scripts\python.exe" -m pip install -r requirements-build.txt
if errorlevel 1 (
    pause
    exit /b 1
)

echo Building portable application files...
".venv\Scripts\python.exe" scripts\build_exe.py
if errorlevel 1 (
    pause
    exit /b 1
)

echo Building one-file installer...
".venv\Scripts\python.exe" scripts\build_native_installer.py
if errorlevel 1 (
    pause
    exit /b 1
)

echo.
echo Done: dist\PigmentSetup.exe
pause
