@echo off
echo ClaudeSync GUI - Debug Launcher
echo ===============================
echo.

cd /d "%~dp0"

echo Checking Python...
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python not found!
    echo Please install Python 3.8 or later
    pause
    exit /b 1
)
echo [OK] Python found

echo.
echo Checking dependencies...
python -c "import customtkinter" >nul 2>&1
if errorlevel 1 (
    echo [!] customtkinter not found - installing...
    python -m pip install customtkinter
)

python -c "import claudesync" >nul 2>&1
if errorlevel 1 (
    echo [!] claudesync not found - installing...
    python -m pip install claudesync[gui]
)

echo.
echo Launching GUI...
echo.
echo === GUI OUTPUT START ===
python -m claudesync.gui.main
echo === GUI OUTPUT END ===

echo.
echo GUI closed. Check above for any errors.
pause
