# start_backend.ps1 - Run FastAPI backend service in current terminal
# Usage: powershell -ExecutionPolicy Bypass -File .\start_backend.ps1

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
$MainModule = "backend.app.main:app"

if (-not (Test-Path $PythonExe)) {
    Write-Host "ERROR: Virtual env Python not found: $PythonExe" -ForegroundColor Red
    Write-Host "Please create the virtual environment: python -m venv .venv" -ForegroundColor Yellow
    exit 1
}

Write-Host "Python : $PythonExe" -ForegroundColor Gray
Write-Host "Module : $MainModule" -ForegroundColor Gray

# ---------------------------------------------------------------------------
# 3. Check port conflict — 智能判断
# ---------------------------------------------------------------------------
$PortCheck = Get-NetTCPConnection -LocalPort 8000 -State Listen -ErrorAction SilentlyContinue | Select-Object -First 1
if ($PortCheck) {
    $pid = $PortCheck.OwningProcess
    $ExistingProc = Get-CimInstance Win32_Process -Filter "ProcessId=$pid" -ErrorAction SilentlyContinue | Select-Object -First 1

    $procName = if ($ExistingProc) { $ExistingProc.Name } else { "未知" }
    $cmdLine  = if ($ExistingProc) { $ExistingProc.CommandLine } else { "" }

    # 判断是否为本项目的 Uvicorn 后端
    $isOwnBackend = ($procName -eq "python.exe" -or $procName -eq "python") -and
                    ($cmdLine -match "backend\.app\.main:app") -and
                    ($cmdLine -match "8000")

    if ($isOwnBackend) {
        Write-Host ""
        Write-Host "============================================" -ForegroundColor Green
        Write-Host "  后端已运行" -ForegroundColor Green
        Write-Host "============================================" -ForegroundColor Green
        Write-Host ""
        Write-Host "  PID      : $pid" -ForegroundColor White
        Write-Host "  Process  : $procName" -ForegroundColor White
        Write-Host "  Command  : $cmdLine" -ForegroundColor Gray
        Write-Host ""
        Write-Host "  Health   : http://127.0.0.1:8000/api/v1/health" -ForegroundColor Cyan
        Write-Host "  API Docs : http://127.0.0.1:8000/docs" -ForegroundColor Cyan
        Write-Host ""
        Write-Host "  无需重复启动，按任意键退出..." -ForegroundColor DarkGray
        $null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")
        exit 0
    }

    # 被其他未知进程占用 — 不自动杀死
    Write-Host ""
    Write-Host "============================================" -ForegroundColor Yellow
    Write-Host "  WARNING: 端口 8000 被其他进程占用" -ForegroundColor Yellow
    Write-Host "============================================" -ForegroundColor Yellow
    Write-Host ""
    Write-Host "  PID      : $pid" -ForegroundColor White
    Write-Host "  Process  : $procName" -ForegroundColor White
    if ($ExistingProc.ExecutablePath) {
        Write-Host "  ExePath  : $($ExistingProc.ExecutablePath)" -ForegroundColor Gray
    }
    Write-Host "  Command  : $cmdLine" -ForegroundColor Gray
    Write-Host ""
    Write-Host "  该进程不是当前项目的后端服务。" -ForegroundColor Yellow
    Write-Host "  请手动停止该进程后再试，或修改 .env 中的 PORT 配置。" -ForegroundColor Yellow
    Write-Host ""
    Write-Host "  按任意键退出..." -ForegroundColor DarkGray
    $null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")
    exit 1
}

# ---------------------------------------------------------------------------
# 4. Start FastAPI
# ---------------------------------------------------------------------------
Write-Host ""
Write-Host "Starting FastAPI backend..." -ForegroundColor Green
Write-Host "API Docs: http://127.0.0.1:8000/docs" -ForegroundColor Cyan
Write-Host "ReDoc   : http://127.0.0.1:8000/redoc" -ForegroundColor Cyan
Write-Host "Press Ctrl+C to stop" -ForegroundColor Gray
Write-Host ""

& $PythonExe -m uvicorn $MainModule --host 127.0.0.1 --port 8000 --reload

Write-Host "FastAPI service stopped." -ForegroundColor Yellow
