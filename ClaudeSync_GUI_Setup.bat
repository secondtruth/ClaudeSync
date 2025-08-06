@echo off
echo ========================================
echo ClaudeSync GUI - Complete Setup and Run
echo ========================================
echo.

cd /d "%~dp0"

echo Step 1: Installing ClaudeSync package...
echo.
python -m pip install -e . --upgrade
if errorlevel 1 (
    echo ERROR: Failed to install ClaudeSync
    echo Please ensure Python is installed and in PATH
    pause
    exit /b 1
)

echo.
echo Step 2: Installing GUI dependencies...
python -m pip install customtkinter pillow --upgrade

echo.
echo Step 3: Running GUI...
echo.
python -m claudesync.gui.main

if errorlevel 1 (
    echo.
    echo === GUI failed to start ===
    echo.
    echo Trying alternative method...
    cd src\claudesync\gui
    python main.py
)

echo.
echo GUI closed.
pause
