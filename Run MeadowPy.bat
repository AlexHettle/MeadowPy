@echo off
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    echo.
    echo  MeadowPy has not been set up yet.
    echo  Please double-click "setup.bat" first.
    echo.
    pause
    exit /b 1
)

.venv\Scripts\python.exe -c "import sys" >nul 2>&1
if %errorlevel% neq 0 (
    echo.
    echo  MeadowPy's virtual environment looks broken.
    echo  Please run "setup.bat" again to recreate it.
    echo.
    pause
    exit /b 1
)

.venv\Scripts\python.exe -m meadowpy
if %errorlevel% neq 0 (
    echo.
    echo MeadowPy failed to start. Press any key to close.
    pause >nul
)
