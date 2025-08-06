# ClaudeSync GUI Launcher with Enhanced Error Reporting
$ErrorActionPreference = "Stop"

Write-Host "ClaudeSync GUI - Enhanced Launcher" -ForegroundColor Cyan
Write-Host "=================================" -ForegroundColor Cyan
Write-Host ""

# Change to script directory
$scriptPath = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $scriptPath
Set-Location "..\..\.."

# Check Python
Write-Host "Checking Python installation..." -ForegroundColor Yellow
try {
    $pythonVersion = python --version 2>&1
    Write-Host "✓ Python found: $pythonVersion" -ForegroundColor Green
} catch {
    Write-Host "✗ Python not found!" -ForegroundColor Red
    Write-Host "Please install Python 3.8 or later" -ForegroundColor Yellow
    Read-Host "Press Enter to exit"
    exit 1
}

# Check GUI dependencies
Write-Host "`nChecking dependencies..." -ForegroundColor Yellow
$modules = @("customtkinter", "PIL", "claudesync")
$missing = @()

foreach ($module in $modules) {
    try {
        python -c "import $module" 2>$null
        Write-Host "✓ $module installed" -ForegroundColor Green
    } catch {
        Write-Host "✗ $module missing" -ForegroundColor Red
        $missing += $module
    }
}

if ($missing.Count -gt 0) {
    Write-Host "`nInstalling missing dependencies..." -ForegroundColor Yellow
    try {
        python -m pip install claudesync[gui] --upgrade
        Write-Host "✓ Dependencies installed" -ForegroundColor Green
    } catch {
        Write-Host "✗ Failed to install dependencies" -ForegroundColor Red
        Write-Host $_.Exception.Message -ForegroundColor Red
    }
}

# Run GUI with error capture
Write-Host "`nLaunching ClaudeSync GUI..." -ForegroundColor Cyan
Write-Host "Check this window for any error messages" -ForegroundColor Yellow
Write-Host ""

try {
    # Try direct module execution
    python -m claudesync.gui.main 2>&1 | ForEach-Object {
        if ($_ -match "error|exception|failed|traceback" -and $_ -notmatch "ErrorActionPreference") {
            Write-Host $_ -ForegroundColor Red
        } else {
            Write-Host $_
        }
    }
} catch {
    Write-Host "`nError launching GUI:" -ForegroundColor Red
    Write-Host $_.Exception.Message -ForegroundColor Red
    Write-Host "`nStack trace:" -ForegroundColor Yellow
    Write-Host $_.ScriptStackTrace -ForegroundColor Gray
    
    # Try alternative launch method
    Write-Host "`nTrying alternative launch method..." -ForegroundColor Yellow
    try {
        Set-Location "src\claudesync\gui"
        python main.py
    } catch {
        Write-Host "Alternative launch also failed" -ForegroundColor Red
        Write-Host $_.Exception.Message -ForegroundColor Red
    }
}

Write-Host "`nGUI closed. Check above for any error messages." -ForegroundColor Yellow
Read-Host "Press Enter to exit"
