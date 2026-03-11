@echo off
where python 2>nul
python --version 2>nul
python -c "import sys; print('EXE:', sys.executable)" 2>nul
python -c "from PyQt6.QtWidgets import QApplication; print('PyQt6 OK')" 2>nul
if %errorlevel% neq 0 (
    echo PyQt6 import failed
    echo.
    echo Checking pip...
    python -m pip show PyQt6 2>nul
)
echo.
echo Press any key to close
pause >nul
