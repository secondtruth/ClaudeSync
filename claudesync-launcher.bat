@echo off
title ClaudeSync GUI v3
color 0A

echo ================================================
echo           ClaudeSync GUI Launcher
echo ================================================
echo.

:: Check if Python is available
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo ERROR: Python is not installed or not in PATH
    echo Please install Python 3.10+ from https://python.org
    pause
    exit /b 1
)

:: Navigate to ClaudeSync directory
cd /d "C:\Users\jordans\Documents\GitHub\ClaudeSync"

:: Check if ClaudeSync is installed
python -c "import claudesync" >nul 2>&1
if %errorlevel% neq 0 (
    echo Installing ClaudeSync...
    pip install -e . --user
)

:: Check for GUI dependencies
python -c "import customtkinter" >nul 2>&1
if %errorlevel% neq 0 (
    echo Installing GUI dependencies...
    pip install customtkinter pillow
)

echo.
echo Launching ClaudeSync GUI...
echo ------------------------------------------------

:: Launch GUI using the integrated command
csync gui

:: Alternative: Launch directly if csync command isn't working
:: python -m claudesync.gui.main

if %errorlevel% neq 0 (
    echo.
    echo GUI failed to launch. Trying alternative method...
    python src\claudesync\gui\gui_main.py
)

pause