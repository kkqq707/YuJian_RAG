# start_web.ps1 - Run Streamlit web service in current terminal
# Usage: powershell -ExecutionPolicy Bypass -File .\start_web.ps1
#
# Equivalent command:
#   & "$PSScriptRoot\.venv\Scripts\python.exe" -m streamlit run "$PSScriptRoot\app.py" --server.address localhost --server.port 8501

$ErrorActionPreference = "Stop"

# ---------------------------------------------------------------------------
# 1. Locate project root (directory of this script)
# ---------------------------------------------------------------------------
$ProjectRoot = $PSScriptRoot
Write-Host "Project Root: $ProjectRoot" -ForegroundColor Cyan

# ---------------------------------------------------------------------------
# 2. Verify required files
# ---------------------------------------------------------------------------
$PythonExe = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
$AppPy     = Join-Path $ProjectRoot "app.py"

if (-not (Test-Path $PythonExe)) {
    Write-Host "ERROR: Virtual env Python not found: $PythonExe" -ForegroundColor Red
    Write-Host "Please create the virtual environment: python -m venv .venv" -ForegroundColor Yellow
    exit 1
}

if (-not (Test-Path $AppPy)) {
    Write-Host "ERROR: app.py not found: $AppPy" -ForegroundColor Red
    exit 1
}

Write-Host "Python : $PythonExe" -ForegroundColor Gray
Write-Host "App    : $AppPy" -ForegroundColor Gray

# ---------------------------------------------------------------------------
# 3. Check port conflict
# ---------------------------------------------------------------------------
$PortCheck = Get-NetTCPConnection -LocalPort 8501 -ErrorAction SilentlyContinue | Select-Object -First 1
if ($PortCheck) {
    $ExistingProc = Get-Process -Id $PortCheck.OwningProcess -ErrorAction SilentlyContinue
    Write-Host "WARNING: Port 8501 is already in use (PID: $($PortCheck.OwningProcess), Process: $($ExistingProc.ProcessName))" -ForegroundColor Yellow
    $choice = Read-Host "Kill the existing process and continue? (y/n)"
    if ($choice -eq 'y' -or $choice -eq 'Y') {
        Stop-Process -Id $PortCheck.OwningProcess -Force -ErrorAction SilentlyContinue
        Write-Host "Old process killed." -ForegroundColor Green
        Start-Sleep -Seconds 1
    } else {
        Write-Host "Startup cancelled." -ForegroundColor Red
        exit 1
    }
}

# ---------------------------------------------------------------------------
# 4. Start Streamlit (foreground, CTRL+C to stop)
# ---------------------------------------------------------------------------
Write-Host ""
Write-Host "Starting Streamlit service..." -ForegroundColor Green
Write-Host "URL: http://localhost:8501" -ForegroundColor Cyan
Write-Host "Press Ctrl+C to stop" -ForegroundColor Gray
Write-Host ""

& $PythonExe -m streamlit run $AppPy `
    --server.address localhost `
    --server.port 8501 `
    --server.headless true

# If we reach here, the service has stopped
Write-Host "Streamlit service stopped." -ForegroundColor Yellow
