# ============================================================
# 企业智库 AI — 启动前端开发服务器
# ============================================================

$ErrorActionPreference = "Stop"
$frontendDir = Join-Path $PSScriptRoot "frontend"

Write-Host "============================================" -ForegroundColor Cyan
Write-Host "  企业智库 AI — 前端启动" -ForegroundColor Cyan
Write-Host "============================================" -ForegroundColor Cyan
Write-Host ""

# ---- 检查 Node.js ----
try {
    $nodeVersion = node --version 2>&1
    Write-Host "[OK] Node.js $nodeVersion" -ForegroundColor Green
} catch {
    Write-Host "[ERROR] Node.js 未安装或不在 PATH 中" -ForegroundColor Red
    Write-Host ""
    Write-Host "请安装 Node.js LTS 版本：" -ForegroundColor Yellow
    Write-Host "  https://nodejs.org/" -ForegroundColor Yellow
    Write-Host ""
    Write-Host "推荐版本：Node.js 20 LTS 或更新版本" -ForegroundColor Yellow
    pause
    exit 1
}

# ---- 检查 npm ----
try {
    $npmVersion = npm --version 2>&1
    Write-Host "[OK] npm $npmVersion" -ForegroundColor Green
} catch {
    Write-Host "[ERROR] npm 不可用" -ForegroundColor Red
    pause
    exit 1
}

Write-Host ""

# ---- 检查 frontend 目录 ----
if (-not (Test-Path $frontendDir)) {
    Write-Host "[ERROR] frontend/ 目录不存在" -ForegroundColor Red
    pause
    exit 1
}

# ---- 检查 node_modules ----
$nodeModulesPath = Join-Path $frontendDir "node_modules"
if (-not (Test-Path $nodeModulesPath)) {
    Write-Host "[WARN] node_modules/ 未找到，正在安装依赖..." -ForegroundColor Yellow
    Set-Location $frontendDir
    npm install
    if ($LASTEXITCODE -ne 0) {
        Write-Host "[ERROR] npm install 失败" -ForegroundColor Red
        pause
        exit 1
    }
    Write-Host "[OK] 依赖安装完成" -ForegroundColor Green
} else {
    Write-Host "[OK] node_modules/ 已存在" -ForegroundColor Green
}

Write-Host ""
Write-Host "[INFO] 启动 Vite 开发服务器..." -ForegroundColor Cyan
Write-Host "[INFO] 前端地址: http://127.0.0.1:5173" -ForegroundColor Cyan
Write-Host "[INFO] API 代理: /api -> http://127.0.0.1:8000" -ForegroundColor Cyan
Write-Host "[INFO] 按 Ctrl+C 停止服务" -ForegroundColor Cyan
Write-Host ""

Set-Location $frontendDir
npm run dev
