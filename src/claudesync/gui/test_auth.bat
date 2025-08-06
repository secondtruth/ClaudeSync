@echo off
echo Testing ClaudeSync Authentication...
echo.
cd /d "%~dp0"
python test_auth_gui.py
pause
