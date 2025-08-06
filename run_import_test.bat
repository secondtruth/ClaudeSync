@echo off
echo Running ClaudeSync import test...
echo.

cd /d "C:\Users\jordans\Documents\GitHub\ClaudeSync"

echo Testing basic Python...
python --version

echo.
echo Testing if ClaudeSync is installed...
pip show claudesync

echo.
echo Testing import from GUI directory...
cd src\claudesync\gui
python test_imports.py

echo.
echo If above failed, trying from root...
cd ..\..\..\
python -m claudesync.gui.test_imports

echo.
echo Done.
pause
