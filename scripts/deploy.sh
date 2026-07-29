#!/bin/bash
# ============================================================
# 企业智库 AI — 安全部署脚本 (Phase 10)
# ============================================================
# 使用:
#   bash scripts/deploy.sh                    # 部署当前分支最新代码
#   bash scripts/deploy.sh <commit>           # 部署指定 commit
#   bash scripts/deploy.sh main --force       # 跳过工作区检查（慎用）
#
# 流程:
#   1. 检查工作区干净
#   2. 记录旧 commit（用于回滚）
#   3. 创建发布前备份
#   4. 拉取最新代码
#   5. 构建镜像
#   6. 运行迁移
#   7. 启动容器
#   8. 等待健康检查
#   9. 执行 smoke test
#   10. 记录部署信息
#
# 失败时停止并提示回滚。
# ============================================================

set -Eeuo pipefail

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

log_info()  { echo -e "${GREEN}[INFO]${NC}  $1"; }
log_warn()  { echo -e "${YELLOW}[WARN]${NC}  $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
DEPLOY_LOG_DIR="${PROJECT_DIR}/deploy_logs"
DEPLOY_TIMESTAMP=$(date +%Y%m%d_%H%M%S)
DEPLOY_LOG="${DEPLOY_LOG_DIR}/deploy_${DEPLOY_TIMESTAMP}.log"

TARGET_REF="${1:-}"
FORCE_MODE=false
if [ "${2:-}" = "--force" ]; then
    FORCE_MODE=true
fi

mkdir -p "${DEPLOY_LOG_DIR}"

# ---- 日志输出同时到控制台和文件 ----
exec > >(tee -a "${DEPLOY_LOG}") 2>&1

echo "============================================"
echo "  企业智库 AI — 安全部署"
echo "  时间: $(date)"
echo "  日志: ${DEPLOY_LOG}"
echo "============================================"
echo ""

cd "${PROJECT_DIR}"

# ---- 1. 检查当前目录 ----
log_info "[1/8] 检查当前目录..."
if [ ! -f "docker-compose.yml" ]; then
    log_error "未找到 docker-compose.yml，请在项目根目录执行此脚本"
    exit 1
fi
log_info "  项目目录: ${PROJECT_DIR}"

# ---- 2. 检查工作区 ----
log_info "[2/8] 检查工作区状态..."

OLD_COMMIT=$(git rev-parse HEAD 2>/dev/null || echo "unknown")
OLD_BRANCH=$(git rev-parse --abbrev-ref HEAD 2>/dev/null || echo "unknown")
log_info "  当前分支: ${OLD_BRANCH}"
log_info "  当前 commit: ${OLD_COMMIT}"

if [ "$FORCE_MODE" = false ]; then
    if ! git diff --quiet 2>/dev/null; then
        log_error "工作区有未提交的修改。"
        log_error "请先提交或暂存修改，或使用 --force 强制部署。"
        log_error ""
        log_error "未跟踪文件:"
        git status --short
        exit 1
    fi
    log_info "  工作区干净 ✓"
else
    log_warn "  --force 模式：跳过工作区检查"
fi

# ---- 3. 创建发布前备份 ----
log_info "[3/8] 创建发布前备份..."
if [ -f "${SCRIPT_DIR}/backup.sh" ]; then
    bash "${SCRIPT_DIR}/backup.sh" || {
        log_warn "备份脚本返回非零，继续部署..."
    }
else
    log_warn "备份脚本不存在，跳过备份"
fi

# ---- 4. 拉取代码 ----
log_info "[4/8] 拉取最新代码..."

if [ -n "$TARGET_REF" ]; then
    log_info "  切换到: ${TARGET_REF}"
    git fetch origin 2>&1 || {
        log_error "git fetch 失败，检查网络连接"
        exit 1
    }
    git checkout "$TARGET_REF" 2>&1 || {
        log_error "git checkout ${TARGET_REF} 失败"
        exit 1
    }
else
    git fetch origin 2>&1 || {
        log_error "git fetch 失败"
        exit 1
    }
    git pull origin "${OLD_BRANCH}" 2>&1 || {
        log_error "git pull 失败"
        exit 1
    }
fi

NEW_COMMIT=$(git rev-parse HEAD)
log_info "  新 commit: ${NEW_COMMIT}"

# ---- 5. 构建镜像 ----
log_info "[5/8] 构建 Docker 镜像..."
docker compose build --no-cache 2>&1 || {
    log_error "Docker 镜像构建失败！"
    log_error "回滚到旧 commit: git checkout ${OLD_COMMIT}"
    git checkout "$OLD_COMMIT"
    exit 1
}
log_info "  镜像构建成功 ✓"

# ---- 6. 运行数据库迁移 ----
log_info "[6/8] 运行数据库迁移..."
# 先启动旧容器（如果停止）以运行迁移
docker compose up -d backend 2>&1 || true

# 等待后端就绪
log_info "  等待后端就绪..."
for i in $(seq 1 30); do
    if curl -sf http://localhost:8000/api/v1/health/live > /dev/null 2>&1; then
        log_info "  后端就绪"
        break
    fi
    if [ "$i" -eq 30 ]; then
        log_error "后端启动超时"
        exit 1
    fi
    sleep 2
done

# 运行迁移
docker compose exec -T backend python -m alembic -c backend/alembic.ini upgrade head 2>&1 || {
    log_error "数据库迁移失败！"
    exit 1
}
log_info "  迁移完成 ✓"

# ---- 7. 启动容器 ----
log_info "[7/8] 启动所有容器..."
docker compose up -d 2>&1 || {
    log_error "容器启动失败！"
    exit 1
}

# ---- 8. 等待健康检查 + Smoke Test ----
log_info "[8/8] 等待健康检查..."

# 等待 backend healthy
log_info "  等待 backend healthy..."
BACKEND_HEALTHY=false
for i in $(seq 1 60); do
    if curl -sf http://localhost:8000/api/v1/health/live > /dev/null 2>&1; then
        BACKEND_HEALTHY=true
        log_info "  Backend healthy ✓"
        break
    fi
    sleep 2
done

if [ "$BACKEND_HEALTHY" = false ]; then
    log_error "Backend 健康检查超时！"
    log_error "检查日志: docker compose logs backend --tail=50"
    log_error ""
    log_error "回滚方法: bash scripts/rollback.sh ${OLD_COMMIT}"
    exit 1
fi

# 等待 frontend healthy
log_info "  等待 frontend healthy..."
FRONTEND_HEALTHY=false
for i in $(seq 1 30); do
    if curl -sf http://localhost/ > /dev/null 2>&1; then
        FRONTEND_HEALTHY=true
        log_info "  Frontend healthy ✓"
        break
    fi
    sleep 2
done

if [ "$FRONTEND_HEALTHY" = false ]; then
    log_error "Frontend 健康检查超时！"
    exit 1
fi

# ---- Smoke Test ----
log_info ""
log_info "执行 Smoke Test..."
if [ -f "${SCRIPT_DIR}/smoke-test.sh" ]; then
    bash "${SCRIPT_DIR}/smoke-test.sh" 2>&1 || {
        log_error "Smoke test 失败！"
        log_error "回滚方法: bash scripts/rollback.sh ${OLD_COMMIT}"
        exit 1
    }
    log_info "Smoke test 通过 ✓"
else
    log_warn "Smoke test 脚本不存在，跳过"
fi

# ---- 记录部署信息 ----
DEPLOY_INFO="${DEPLOY_LOG_DIR}/deploy_info.txt"
cat > "${DEPLOY_INFO}" << INFO_EOF
Deploy Time:     $(date -u +%Y-%m-%dT%H:%M:%SZ)
Old Commit:      ${OLD_COMMIT}
New Commit:      ${NEW_COMMIT}
Branch:          ${OLD_BRANCH}
Deploy Log:      ${DEPLOY_LOG}
Status:          SUCCESS
INFO_EOF

echo ""
echo "============================================"
echo -e "${GREEN}  部署成功！${NC}"
echo "============================================"
echo "  旧 commit: ${OLD_COMMIT}"
echo "  新 commit: ${NEW_COMMIT}"
echo "  部署日志: ${DEPLOY_LOG}"
echo ""
echo "回滚命令:"
echo "  bash scripts/rollback.sh ${OLD_COMMIT}"
echo "============================================"
