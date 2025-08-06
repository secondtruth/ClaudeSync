@echo off
echo Testing ClaudeSync Simple GUI...
echo.
echo This will test if the Simple GUI can launch properly.
echo Press Ctrl+C to cancel.
echo.
pause

cd /d "%~dp0"

echo Checking Python...
python --version
if %ERRORLEVEL% NEQ 0 (
    echo ERROR: Python not found!
    pause
    exit /b 1
)

echo.
echo Checking customtkinter...
python -c "import customtkinter; print('customtkinter OK')"
if %ERRORLEVEL% NEQ 0 (
    echo ERROR: customtkinter not installed!
    echo Run: pip install customtkinter
    pause
    exit /b 1
)

echo.
echo Checking ClaudeSync...
where csync >nul 2>&1
if %ERRORLEVEL% EQU 0 (
    echo csync command found OK
) else (
    echo WARNING: csync command not found
    echo ClaudeSync might not be installed globally
)

echo.
echo All checks passed! Launching Simple GUI...
echo.
python simple_gui.py

pause
