@echo off
setlocal enabledelayedexpansion

set "EXIT_CODE=0"
set "SCRIPT_DIR=%~dp0"
pushd "%SCRIPT_DIR%.." >nul

echo ========================================
echo    ClaudeSync GUI Setup and Launcher

echo ========================================
echo.

echo Checking Python installation...
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python is not installed or not in PATH.
    echo Please install Python 3.10 or later from https://python.org
    set "EXIT_CODE=1"
    goto :cleanup
)

echo Preparing GUI dependencies (customtkinter, pillow)...
python -m scripts.launch_gui --deps-only --verbose
if errorlevel 1 (
    echo ERROR: Unable to prepare GUI dependencies.
    set "EXIT_CODE=1"
    goto :cleanup
)

echo.
echo Launching ClaudeSync GUI...
python -m scripts.launch_gui --verbose
set "EXIT_CODE=%errorlevel%"
if not "%EXIT_CODE%"=="0" (
    echo.
    echo ERROR: Failed to launch GUI (exit code %EXIT_CODE%).
    echo Try running: python -m claudesync.gui.main
)

echo.
pause

:cleanup
popd >nul
endlocal
exit /b %EXIT_CODE%
