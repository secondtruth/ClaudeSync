# ClaudeSync GUI Launcher with Enhanced Error Reporting
Continue = "Stop"

Write-Host "ClaudeSync GUI - Enhanced Launcher" -ForegroundColor Cyan
Write-Host "=================================" -ForegroundColor Cyan
Write-Host ""

 = Split-Path -Parent System.Management.Automation.InvocationInfo.MyCommand.Path
 = (Resolve-Path (Join-Path  ".." )).Path
Push-Location 

try {
    Write-Host "Checking Python installation..." -ForegroundColor Yellow
    try {
         = python --version 2>&1
        Write-Host "[OK] Python found: " -ForegroundColor Green
    } catch {
        Write-Host "[ERROR] Python not found." -ForegroundColor Red
        Write-Host "Install Python 3.10 or later and ensure it is on PATH." -ForegroundColor Yellow
        throw
    }

    Write-Host "
Preparing GUI dependencies..." -ForegroundColor Yellow
     = & python -m scripts.launch_gui --deps-only --verbose 2>&1
     | ForEach-Object {
        if ( -match "error|exception|failed|traceback") {
            Write-Host  -ForegroundColor Red
        } else {
            Write-Host 
        }
    }
    if (0 -ne 0) {
        Write-Host "[ERROR] Failed to prepare GUI dependencies." -ForegroundColor Red
        throw "Dependency preparation failed"
    }

    Write-Host "
Launching ClaudeSync GUI (direct import mode)..." -ForegroundColor Cyan
    python -m scripts.launch_gui --verbose --no-cli 2>&1 | ForEach-Object {
        if ( -match "error|exception|failed|traceback") {
            Write-Host  -ForegroundColor Red
        } else {
            Write-Host 
        }
    }
    if (0 -ne 0) {
        Write-Host "
[ERROR] GUI exited with code 0" -ForegroundColor Red
    }

    Write-Host "
GUI closed. Check above for any error messages." -ForegroundColor Yellow
    Read-Host "Press Enter to exit"
}
finally {
    Pop-Location
}
