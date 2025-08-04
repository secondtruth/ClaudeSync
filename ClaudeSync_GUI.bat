@echo off
setlocal enabledelayedexpansion

echo ========================================
echo    ClaudeSync GUI Setup and Launcher
echo ========================================
echo.

cd /d "%~dp0"

:: Check Python installation
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python is not installed or not in PATH!
    echo Please install Python 3.10 or later from python.org
    pause
    exit /b 1
)

:: Check and install dependencies
echo Checking dependencies...
python -c "import customtkinter" >nul 2>&1
if errorlevel 1 (
    echo Installing GUI dependencies...
    pip install customtkinter pillow
    if errorlevel 1 (
        echo ERROR: Failed to install dependencies
        echo Try running: pip install --upgrade pip
        pause
        exit /b 1
    )
) else (
    echo Dependencies already installed.
)

:: Check ClaudeSync installation
echo.
echo Checking ClaudeSync installation...
python -c "import claudesync" >nul 2>&1
if errorlevel 1 (
    echo Installing ClaudeSync...
    pip install -e .
    if errorlevel 1 (
        echo ERROR: Failed to install ClaudeSync
        pause
        exit /b 1
    )
) else (
    echo ClaudeSync already installed.
)

:: Launch GUI
echo.
echo ========================================
echo      Launching ClaudeSync GUI...
echo ========================================
echo.

python launch_gui.py

if errorlevel 1 (
    echo.
    echo ERROR: Failed to launch GUI
    echo Try running: python test_gui_imports.py
    pause
)
