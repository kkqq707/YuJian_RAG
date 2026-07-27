# ============================================================
# 企业智库 AI — 同时启动前后端开发服务器
# ============================================================

$ErrorActionPreference = "Stop"

Write-Host "============================================" -ForegroundColor Cyan
Write-Host "  企业智库 AI — 开发环境启动" -ForegroundColor Cyan
Write-Host "============================================" -ForegroundColor Cyan
Write-Host ""

$rootDir = $PSScriptRoot
$HealthUrl = "http://127.0.0.1:8000/api/v1/health"
$BackendRunning = $false

# ---- 检查 Node.js ----
try {
    $nodeVersion = node --version 2>&1
    Write-Host "[OK] Node.js $nodeVersion" -ForegroundColor Green
} catch {
    Write-Host "[ERROR] Node.js 未安装" -ForegroundColor Red
    pause
    exit 1
}

# ---- 检查 Python ----
try {
    $pyVersion = python --version 2>&1
    Write-Host "[OK] Python $pyVersion" -ForegroundColor Green
} catch {
    Write-Host "[ERROR] Python 未安装" -ForegroundColor Red
    pause
    exit 1
}

Write-Host ""

# ---- 健康检查：判断后端是否已运行 ----
Write-Host "[INFO] 检查后端服务状态..." -ForegroundColor Cyan

try {
    $response = Invoke-WebRequest -Uri $HealthUrl -Method GET -TimeoutSec 3 -ErrorAction Stop
    if ($response.StatusCode -eq 200) {
        Write-Host "[OK] 后端已运行: $HealthUrl -> 200" -ForegroundColor Green
        $BackendRunning = $true
    }
} catch {
    Write-Host "[INFO] 后端未运行 (health check failed: $($_.Exception.Message))" -ForegroundColor Yellow
}

# ---- 启动后端（仅在未运行时） ----
if (-not $BackendRunning) {
    $backendScript = Join-Path $rootDir "start_backend.ps1"
    if (Test-Path $backendScript) {
        Write-Host "[INFO] 启动后端服务 (端口 8000)..." -ForegroundColor Cyan
        Start-Process powershell -ArgumentList "-NoExit", "-ExecutionPolicy", "Bypass", "-File", "`"$backendScript`"" -WindowStyle Normal

        # 轮询等待后端健康检查通过
        $maxWait = 30
        $waited = 0
        Write-Host "[INFO] 等待后端服务就绪..." -ForegroundColor Cyan
        do {
            Start-Sleep -Seconds 2
            $waited += 2
            try {
                $resp = Invoke-WebRequest -Uri $HealthUrl -Method GET -TimeoutSec 2 -ErrorAction Stop
                if ($resp.StatusCode -eq 200) {
                    Write-Host "[OK] 后端服务已就绪 (等待 ${waited}s)" -ForegroundColor Green
                    $BackendRunning = $true
                    break
                }
            } catch {
                # 继续等待
            }
            Write-Host "  ... 等待中 (${waited}s / ${maxWait}s)" -ForegroundColor Gray
        } while ($waited -lt $maxWait)

        if (-not $BackendRunning) {
            Write-Host "[WARN] 后端在 ${maxWait}s 内未就绪，仍将启动前端" -ForegroundColor Yellow
        }
    } else {
        Write-Host "[WARN] start_backend.ps1 未找到，跳过后端启动" -ForegroundColor Yellow
        Write-Host "[INFO] 请手动启动后端: python -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000 --reload" -ForegroundColor Yellow
    }
} else {
    Write-Host "[INFO] 后端已在运行，跳过启动" -ForegroundColor Cyan
}

# ---- 启动前端（新窗口） ----
$frontendScript = Join-Path $rootDir "start_frontend.ps1"
if (Test-Path $frontendScript) {
    Write-Host "[INFO] 启动前端服务 (端口 5173)..." -ForegroundColor Cyan
    Start-Process powershell -ArgumentList "-NoExit", "-ExecutionPolicy", "Bypass", "-File", "`"$frontendScript`"" -WindowStyle Normal
    Write-Host "[OK] 前端服务已在独立窗口中启动" -ForegroundColor Green
} else {
    Write-Host "[ERROR] start_frontend.ps1 未找到" -ForegroundColor Red
    pause
    exit 1
}

Write-Host ""
Write-Host "============================================" -ForegroundColor Cyan
Write-Host "  开发环境已启动" -ForegroundColor Green
Write-Host "============================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "  后端: http://127.0.0.1:8000" -ForegroundColor White
Write-Host "  前端: http://127.0.0.1:5173" -ForegroundColor White
Write-Host "  API 文档: http://127.0.0.1:8000/docs" -ForegroundColor White
Write-Host ""
Write-Host "  浏览器打开: http://127.0.0.1:5173" -ForegroundColor Yellow
Write-Host ""
Write-Host "  按任意键关闭此窗口（不会关闭前后端服务）" -ForegroundColor DarkGray

$null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")
