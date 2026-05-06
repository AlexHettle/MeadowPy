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

set "MEADOWPY_LOG_DIR=%USERPROFILE%\.meadowpy"
set "MEADOWPY_LOG=%MEADOWPY_LOG_DIR%\meadowpy.log"
if not exist "%MEADOWPY_LOG_DIR%" mkdir "%MEADOWPY_LOG_DIR%" >nul 2>&1
echo.>> "%MEADOWPY_LOG%"
echo [%date% %time%] Launching MeadowPy>> "%MEADOWPY_LOG%"

.venv\Scripts\python.exe -X faulthandler -m meadowpy >> "%MEADOWPY_LOG%" 2>&1
set "MEADOWPY_EXIT_CODE=%errorlevel%"
if %MEADOWPY_EXIT_CODE% neq 0 (
    echo.
    echo MeadowPy closed with an error ^(exit code %MEADOWPY_EXIT_CODE%^).
    echo Check "%MEADOWPY_LOG%" for shutdown details.
    echo Press any key to close.
    pause >nul
    exit /b %MEADOWPY_EXIT_CODE%
)
