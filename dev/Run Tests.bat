@echo off
setlocal

for %%I in ("%~dp0..") do set "PROJECT_ROOT=%%~fI"
cd /d "%PROJECT_ROOT%"

if not exist ".venv\Scripts\python.exe" (
    echo.
    echo  MeadowPy has not been set up for development yet.
    echo  Please run "dev\setup-dev.bat" or "setup.bat --dev" first.
    echo.
    pause
    exit /b 1
)

.venv\Scripts\python.exe -c "import pytest" >nul 2>&1
if %errorlevel% neq 0 (
    echo.
    echo  Test dependencies are missing.
    echo  Please run "dev\setup-dev.bat" or "setup.bat --dev" first.
    echo.
    pause
    exit /b 1
)

set "QT_QPA_PLATFORM=offscreen"
.venv\Scripts\python.exe -m pytest -c dev\pytest.ini --cov-report=html:dev\htmlcov %*
set "EXIT_CODE=%errorlevel%"

echo.
echo  HTML coverage report: dev\htmlcov\index.html
echo  XML coverage report:  dev\coverage.xml
echo.
if %EXIT_CODE% equ 0 (
    echo  Tests passed. Press any key to close.
) else (
    echo  Tests finished with failures. Press any key to close.
)

if not defined MEADOWPY_NO_PAUSE (
    pause >nul
)
exit /b %EXIT_CODE%
