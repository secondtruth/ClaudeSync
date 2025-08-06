@echo off
:: ClaudeSync Simple GUI Launcher
:: Place this in ClaudeSync root directory

echo Starting ClaudeSync Simple GUI...
cd /d "%~dp0"
python gui-simple\simple_gui.py

if %ERRORLEVEL% NEQ 0 (
    echo.
    echo Failed to start Simple GUI
    echo.
    echo Please ensure:
    echo 1. Python is installed
    echo 2. customtkinter is installed: pip install customtkinter
    echo 3. ClaudeSync is installed: pip install claudesync
    echo.
    pause
)
