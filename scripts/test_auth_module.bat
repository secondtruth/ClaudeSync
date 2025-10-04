@echo off
setlocal

set "SCRIPT_DIR=%~dp0"
pushd "%SCRIPT_DIR%.." >nul

set "PYTHONPATH=%CD%\src;%PYTHONPATH%"

echo Testing ClaudeSync authentication module...
echo.

echo Test 1: Import check
python -c "from claudesync.gui.auth_handler import AuthHandler; print('OK: Import successful')"
if errorlevel 1 (
    echo ERROR: Import failed. Is the project installed or src on PYTHONPATH?
    goto :cleanup
)

echo.
echo Test 2: Create auth handler instance
python -c "from claudesync.gui.auth_handler import AuthHandler; _ = AuthHandler(); print('OK: AuthHandler created')"
if errorlevel 1 (
    echo ERROR: Failed to instantiate AuthHandler.
    goto :cleanup
)

echo.
echo Test 3: Check current status
python -m claudesync.gui.debug_auth

if errorlevel 1 (
    echo DEBUG: auth diagnostics exited with code %errorlevel%.
)

echo.
echo To test authentication with a specific key, run:
echo   python -m claudesync.gui.debug_auth YOUR_SESSION_KEY

echo Or try the test GUI:
echo   python -m claudesync.gui.test_auth_gui

echo.
pause

:cleanup
popd >nul
endlocal

