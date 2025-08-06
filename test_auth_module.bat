@echo off
echo Testing ClaudeSync Authentication Module...
echo.

cd /d "%~dp0"

echo Test 1: Import check
python -c "from src.claudesync.gui.auth_handler import AuthHandler; print('✓ Import successful')"
if errorlevel 1 (
    echo ✗ Import failed!
    echo.
    echo Trying alternative path...
    cd src\claudesync\gui
    python -c "from auth_handler import AuthHandler; print('✓ Import successful')"
)

echo.
echo Test 2: Create auth handler instance
python -c "from src.claudesync.gui.auth_handler import AuthHandler; auth = AuthHandler(); print('✓ AuthHandler created')"

echo.
echo Test 3: Check current status
python src\claudesync\gui\debug_auth.py

echo.
echo To test authentication, run:
echo   python src\claudesync\gui\debug_auth.py YOUR_SESSION_KEY
echo.
echo Or try the test GUI:
echo   python src\claudesync\gui\test_auth_gui.py
echo.
pause
