@echo off
setlocal enabledelayedexpansion
cd /d "%~dp0"

echo.
echo  =============================================
echo     MeadowPy Setup
echo  =============================================
echo.

:: -----------------------------------------------------------
:: 1. Find Python 3.11+
:: -----------------------------------------------------------
set "PYTHON_CMD="

:: Try py launcher first (most reliable on Windows)
py -3 --version >nul 2>&1
if %errorlevel% equ 0 (
    set "PYTHON_CMD=py -3"
    goto :check_version
)

:: Try python
python --version >nul 2>&1
if %errorlevel% equ 0 (
    set "PYTHON_CMD=python"
    goto :check_version
)

:: Try python3
python3 --version >nul 2>&1
if %errorlevel% equ 0 (
    set "PYTHON_CMD=python3"
    goto :check_version
)

echo  [ERROR] Python was not found on this computer.
echo.
echo  Please install Python 3.11 or newer from:
echo    https://www.python.org/downloads/
echo.
echo  IMPORTANT: Check the box that says
echo    "Add Python to PATH" during installation.
echo.
pause
exit /b 1

:: -----------------------------------------------------------
:: 2. Verify version is 3.11+
:: -----------------------------------------------------------
:check_version
for /f "tokens=2 delims= " %%v in ('%PYTHON_CMD% --version 2^>^&1') do set "PY_VER=%%v"

for /f "tokens=1,2 delims=." %%a in ("%PY_VER%") do (
    set "PY_MAJOR=%%a"
    set "PY_MINOR=%%b"
)

if !PY_MAJOR! lss 3 goto :bad_version
if !PY_MAJOR! equ 3 if !PY_MINOR! lss 11 goto :bad_version

echo  Found Python %PY_VER%
echo.
goto :setup_venv

:bad_version
echo  [ERROR] Python %PY_VER% was found, but MeadowPy requires 3.11 or newer.
echo.
echo  Please download a newer version from:
echo    https://www.python.org/downloads/
echo.
pause
exit /b 1

:: -----------------------------------------------------------
:: 3. Create virtual environment
:: -----------------------------------------------------------
:setup_venv
if exist ".venv\Scripts\python.exe" (
    echo  Virtual environment already exists — skipping creation.
) else (
    if exist ".venv" (
        echo  Found a broken virtual environment — recreating...
        rmdir /s /q .venv
    )
    echo  Creating virtual environment...
    %PYTHON_CMD% -m venv .venv
    if %errorlevel% neq 0 (
        echo.
        echo  [ERROR] Failed to create virtual environment.
        echo  Please make sure Python is installed correctly.
        pause
        exit /b 1
    )
)

:: -----------------------------------------------------------
:: 4. Install dependencies
:: -----------------------------------------------------------
echo  Upgrading pip...
.venv\Scripts\python.exe -m pip install --upgrade pip -q
echo  Installing dependencies...
.venv\Scripts\python.exe -m pip install -r requirements.txt -q
if %errorlevel% neq 0 (
    echo.
    echo  [ERROR] Failed to install dependencies.
    echo  Check your internet connection and try again.
    pause
    exit /b 1
)

:: -----------------------------------------------------------
:: 5. Quick verification
:: -----------------------------------------------------------
.venv\Scripts\python.exe -c "from PyQt6.QtWidgets import QApplication" >nul 2>&1
if %errorlevel% neq 0 (
    echo.
    echo  [WARNING] PyQt6 installed but could not be verified.
    echo  MeadowPy may still work — try launching it.
    echo.
)

:: -----------------------------------------------------------
:: 6. Create desktop-style shortcut with icon
:: -----------------------------------------------------------
echo  Creating MeadowPy shortcut...
set "SCRIPT_DIR=%~dp0"
:: Remove trailing backslash for clean paths
if "%SCRIPT_DIR:~-1%"=="\" set "SCRIPT_DIR=%SCRIPT_DIR:~0,-1%"

powershell -NoProfile -Command ^
  "$ws = New-Object -ComObject WScript.Shell;" ^
  "$s = $ws.CreateShortcut('%SCRIPT_DIR%\MeadowPy.lnk');" ^
  "$s.TargetPath = '%SCRIPT_DIR%\launch.vbs';" ^
  "$s.WorkingDirectory = '%SCRIPT_DIR%';" ^
  "$s.IconLocation = '%SCRIPT_DIR%\meadowpy\resources\icons\meadowpy.ico,0';" ^
  "$s.Description = 'Launch MeadowPy IDE';" ^
  "$s.Save()"

if exist "MeadowPy.lnk" (
    echo  Shortcut created successfully.
) else (
    echo  [WARNING] Could not create shortcut. You can still use "Run MeadowPy.bat".
)

:: -----------------------------------------------------------
:: Done
:: -----------------------------------------------------------
echo.
echo  =============================================
echo     Setup complete!
echo.
echo     Double-click "MeadowPy" to start.
echo  =============================================
echo.
pause
