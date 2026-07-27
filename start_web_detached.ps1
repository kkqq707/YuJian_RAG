# start_web_detached.ps1 - Launch Streamlit in a separate PowerShell window
# Usage: powershell -ExecutionPolicy Bypass -File .\start_web_detached.ps1
# The script returns immediately; the Streamlit window stays open.

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
    Write-Host "Please stop the existing process first:" -ForegroundColor Yellow
    Write-Host "  taskkill /PID $($PortCheck.OwningProcess) /F" -ForegroundColor Gray
    exit 1
}

# ---------------------------------------------------------------------------
# 4. Build the command for the new window
# ---------------------------------------------------------------------------
$Py = $PythonExe
$App = $AppPy

# Build a script block that the new window will execute
$InnerScript = @"
`$Host.UI.RawUI.WindowTitle = 'Streamlit - Enterprise Knowledge Q&A (localhost:8501)'
Write-Host '========================================' -ForegroundColor Cyan
Write-Host '  Streamlit Enterprise Knowledge Q&A' -ForegroundColor Green
Write-Host '  URL: http://localhost:8501' -ForegroundColor Cyan
Write-Host '  Close this window or Ctrl+C to stop' -ForegroundColor Gray
Write-Host '========================================' -ForegroundColor Cyan
Write-Host ''
Write-Host "Project: $ProjectRoot" -ForegroundColor Gray
Write-Host ''

try {
    & '$Py' -m streamlit run '$App' --server.address localhost --server.port 8501 --server.headless true
    Write-Host ''
    Write-Host 'Streamlit service stopped.' -ForegroundColor Yellow
} catch {
    Write-Host "Streamlit exited: `$(`$_.Exception.Message)" -ForegroundColor Red
}

Write-Host ''
Read-Host 'Press Enter to close this window'
"@

# Write the inner script to a temp file to avoid encoding issues
$TempScript = Join-Path $env:TEMP "streamlit_launcher.ps1"
$InnerScript | Out-File -FilePath $TempScript -Encoding UTF8

# ---------------------------------------------------------------------------
# 5. Launch independent window
# ---------------------------------------------------------------------------
Write-Host ""
Write-Host "Launching Streamlit in a new window..." -ForegroundColor Green

Start-Process powershell.exe -ArgumentList @(
    "-NoExit",
    "-ExecutionPolicy", "Bypass",
    "-File", $TempScript
)

Write-Host "Streamlit launched in a separate window." -ForegroundColor Green
Write-Host "Browser URL: http://localhost:8501" -ForegroundColor Cyan
Write-Host "Closing this terminal will NOT stop Streamlit." -ForegroundColor Gray
