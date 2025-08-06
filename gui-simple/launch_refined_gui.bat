@echo off
title ClaudeSync Refined GUI
echo Starting ClaudeSync Refined GUI...
cd /d "%~dp0"
python refined_gui.py
if errorlevel 1 (
    echo.
    echo Error occurred. Press any key to exit...
    pause > nul
)
