@echo off
setlocal
cd /d "%~dp0"
set "PYTHONUTF8=1"

set "PYTHON="
if exist "%USERPROFILE%\.dsh\dsh-runtimes\dsh-primary-runtime\dependencies\python\python.exe" (
    set "PYTHON=%USERPROFILE%\.dsh\dsh-runtimes\dsh-primary-runtime\dependencies\python\python.exe"
    goto python_found
)

where py >nul 2>nul
if not errorlevel 1 (
    set "PYTHON=py -3"
    goto python_found
)

where python >nul 2>nul
if not errorlevel 1 (
    set "PYTHON=python"
    goto python_found
)

echo Python 3 not found.
echo Install Python 3.10+ from python.org and enable "Add Python to PATH".
exit /b 1

:python_found
%PYTHON% --version >nul 2>nul
if errorlevel 1 (
    echo Could not start Python.
    exit /b 1
)

if not exist ".venv\Scripts\python.exe" (
    echo Creating virtual environment...
    %PYTHON% -m venv .venv
    if errorlevel 1 exit /b 1
)

echo Installing dependencies...
".venv\Scripts\python.exe" -m pip install --upgrade pip
if errorlevel 1 exit /b 1
".venv\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 exit /b 1

echo.
echo Done. Launch run.bat.
