@echo off
echo Starting ClaudeSync Simple GUI...

:: Navigate to the ClaudeSync directory
cd /d "%~dp0\.."

:: Try to run with csync first (if installed)
where csync >nul 2>&1
if %ERRORLEVEL% EQU 0 (
    echo Found csync command
    python gui-simple\simple_gui.py
) else (
    :: Try with python module
    echo Running with Python module...
    python -m gui-simple.simple_gui
)

if %ERRORLEVEL% NEQ 0 (
    echo.
    echo Error: Failed to start GUI
    echo Make sure Python and ClaudeSync are installed
    pause
)
