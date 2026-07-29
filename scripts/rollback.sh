#!/bin/bash
# ============================================================
# 企业智库 AI — 安全回滚脚本 (Phase 10)
# ============================================================
# 使用:
#   bash scripts/rollback.sh <commit>              # 回滚代码和镜像
#   bash scripts/rollback.sh <commit> --restore-db # 同时恢复数据库
#
# 流程:
#   1. 记录当前状态（故障现场）
#   2. 切换到目标 commit
#   3. 重新构建镜像
#   4. 启动容器
#   5. 健康检查
#   6. (可选) 恢复数据库 — 需显式确认
#
# 默认不自动恢复数据库！
# Alembic downgrade 不自动执行！
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
ROLLBACK_LOG_DIR="${PROJECT_DIR}/deploy_logs"
ROLLBACK_TIMESTAMP=$(date +%Y%m%d_%H%M%S)
ROLLBACK_LOG="${ROLLBACK_LOG_DIR}/rollback_${ROLLBACK_TIMESTAMP}.log"

TARGET_COMMIT="${1:-}"
RESTORE_DB=false
if [ "${2:-}" = "--restore-db" ]; then
    RESTORE_DB=true
fi

mkdir -p "${ROLLBACK_LOG_DIR}"

exec > >(tee -a "${ROLLBACK_LOG}") 2>&1

echo "============================================"
echo "  企业智库 AI — 安全回滚"
echo "  时间: $(date)"
echo "  日志: ${ROLLBACK_LOG}"
echo "============================================"
echo ""

if [ -z "$TARGET_COMMIT" ]; then
    log_error "请指定目标 commit"
    echo ""
    echo "用法: bash scripts/rollback.sh <commit> [--restore-db]"
    echo ""
    echo "最近部署记录:"
    if [ -f "${ROLLBACK_LOG_DIR}/deploy_info.txt" ]; then
        cat "${ROLLBACK_LOG_DIR}/deploy_info.txt"
    fi
    echo ""
    echo "最近 git 日志:"
    git log --oneline -10
    exit 1
fi

cd "${PROJECT_DIR}"

# ---- 1. 记录当前状态（故障现场保留） ----
log_info "[1/6] 记录当前状态..."
CURRENT_COMMIT=$(git rev-parse HEAD)
CURRENT_BRANCH=$(git rev-parse --abbrev-ref HEAD)
log_info "  当前 commit: ${CURRENT_COMMIT}"
log_info "  目标 commit: ${TARGET_COMMIT}"
log_info "  当前分支:   ${CURRENT_BRANCH}"

# 保存当前日志（故障现场）
LOG_ARCHIVE="${ROLLBACK_LOG_DIR}/pre_rollback_logs_${ROLLBACK_TIMESTAMP}"
mkdir -p "${LOG_ARCHIVE}"

if docker compose ps backend 2>/dev/null | grep -q "backend"; then
    docker compose logs --tail=200 backend > "${LOG_ARCHIVE}/backend_pre_rollback.log" 2>/dev/null || true
    docker compose logs --tail=100 frontend > "${LOG_ARCHIVE}/frontend_pre_rollback.log" 2>/dev/null || true
    log_info "  故障现场日志已保存: ${LOG_ARCHIVE}"
fi

# ---- 2. 数据库恢复确认（如指定） ----
if [ "$RESTORE_DB" = true ]; then
    echo ""
    echo -e "${RED}============================================${NC}"
    echo -e "${RED}  ⚠  数据库恢复确认${NC}"
    echo -e "${RED}============================================${NC}"
    echo ""
    echo "你指定了 --restore-db 选项。"
    echo "这将用备份中的数据库替换当前数据库。"
    echo ""
    echo "Alembic downgrade 不会自动执行。"
    echo "如果新版本 schema 与旧版本不兼容，"
    echo "你需要手动执行 migration downgrade。"
    echo ""

    # 先备份当前数据库
    log_info "恢复前备份当前数据库..."
    if [ -f "${SCRIPT_DIR}/backup.sh" ]; then
        bash "${SCRIPT_DIR}/backup.sh" || log_warn "备份失败，继续..."
    fi

    echo ""
    read -r -p "确认恢复数据库? 输入 'yes' 继续: " CONFIRM
    if [ "$CONFIRM" != "yes" ]; then
        log_info "取消数据库恢复，仅回滚代码和镜像"
        RESTORE_DB=false
    else
        log_warn "数据库恢复将在代码回滚后执行"
    fi
fi

# ---- 3. 切换代码 ----
log_info "[2/6] 切换代码到 ${TARGET_COMMIT}..."
git fetch origin 2>&1 || true
git checkout "$TARGET_COMMIT" 2>&1 || {
    log_error "git checkout 失败！"
    exit 1
}
log_info "  已切换到: $(git rev-parse HEAD)"

# ---- 4. 重建镜像 ----
log_info "[3/6] 重建 Docker 镜像..."
docker compose build --no-cache 2>&1 || {
    log_error "镜像构建失败！"
    exit 1
}
log_info "  镜像构建完成 ✓"

# ---- 5. 启动容器 ----
log_info "[4/6] 停止当前容器..."
docker compose down 2>&1 || true

log_info "启动回滚版本..."
docker compose up -d 2>&1 || {
    log_error "容器启动失败！"
    exit 1
}

# ---- 6. 健康检查 ----
log_info "[5/6] 等待健康检查..."

BACKEND_OK=false
for i in $(seq 1 60); do
    if curl -sf http://localhost:8000/api/v1/health/live > /dev/null 2>&1; then
        BACKEND_OK=true
        break
    fi
    sleep 2
done

if [ "$BACKEND_OK" = false ]; then
    log_error "Backend 健康检查失败！"
    log_error "请检查日志: docker compose logs backend --tail=50"
    log_error "故障现场日志: ${LOG_ARCHIVE}"
    exit 1
fi
log_info "  Backend OK ✓"

FRONTEND_OK=false
for i in $(seq 1 30); do
    if curl -sf http://localhost/ > /dev/null 2>&1; then
        FRONTEND_OK=true
        break
    fi
    sleep 2
done

if [ "$FRONTEND_OK" = false ]; then
    log_warn "Frontend 健康检查失败（不影响 API）"
else
    log_info "  Frontend OK ✓"
fi

# ---- 7. 数据库恢复（如确认） ----
if [ "$RESTORE_DB" = true ]; then
    log_info "[6/6] 恢复数据库..."

    # 列出可用备份
    echo ""
    echo "可用备份:"
    ls -1t "${PROJECT_DIR}/backups"/backup_*.tar.gz 2>/dev/null | head -5 || echo "  (无)"

    echo ""
    read -r -p "输入要恢复的 backup_id（留空跳过）: " RESTORE_BACKUP_ID

    if [ -n "$RESTORE_BACKUP_ID" ]; then
        RESTORE_FILE="${PROJECT_DIR}/backups/${RESTORE_BACKUP_ID}.tar.gz"
        if [ -f "$RESTORE_FILE" ]; then
            log_info "恢复: ${RESTORE_BACKUP_ID}"

            # 停止后端
            docker compose stop backend 2>&1 || true

            # 解压
            TEMP_RESTORE="${PROJECT_DIR}/_rollback_restore"
            rm -rf "$TEMP_RESTORE"
            mkdir -p "$TEMP_RESTORE"
            tar xzf "$RESTORE_FILE" -C "$TEMP_RESTORE"

            RESTORE_DIR="${TEMP_RESTORE}/${RESTORE_BACKUP_ID}"

            # 恢复数据库
            if [ -f "${RESTORE_DIR}/storage/app.db" ]; then
                docker run --rm \
                    -v yujian_storage:/mnt/storage \
                    -v "${RESTORE_DIR}:/restore:ro" \
                    alpine:latest \
                    sh -c "cp /restore/storage/app.db /mnt/storage/app.db"

                log_info "  数据库已恢复"

                # 恢复 Chroma
                if [ -d "${RESTORE_DIR}/storage/chroma_db" ]; then
                    docker run --rm \
                        -v yujian_storage:/mnt/storage \
                        -v "${RESTORE_DIR}:/restore:ro" \
                        alpine:latest \
                        sh -c "rm -rf /mnt/storage/chroma_db && cp -r /restore/storage/chroma_db /mnt/storage/chroma_db"

                    log_info "  Chroma 已恢复"
                fi
            else
                log_warn "  备份中无数据库文件"
            fi

            # 清理
            rm -rf "$TEMP_RESTORE"

            # 重启后端
            docker compose start backend 2>&1 || true

            # 等待健康
            for i in $(seq 1 30); do
                if curl -sf http://localhost:8000/api/v1/health/live > /dev/null 2>&1; then
                    log_info "  数据库恢复后 Backend OK ✓"
                    break
                fi
                sleep 2
            done
        else
            log_error "备份文件不存在: ${RESTORE_FILE}"
        fi
    else
        log_info "跳过数据库恢复"
    fi
fi

# ---- 记录回滚信息 ----
cat >> "${ROLLBACK_LOG_DIR}/deploy_info.txt" << INFO_EOF
Rollback Time:  $(date -u +%Y-%m-%dT%H:%M:%SZ)
From Commit:    ${CURRENT_COMMIT}
To Commit:      $(git rev-parse HEAD)
Rollback Log:   ${ROLLBACK_LOG}
DB Restored:    ${RESTORE_DB}
Status:         SUCCESS
INFO_EOF

echo ""
echo "============================================"
echo -e "${GREEN}  回滚完成！${NC}"
echo "============================================"
echo "  回滚到: $(git rev-parse HEAD)"
echo "  日志:   ${ROLLBACK_LOG}"
echo "  故障现场: ${LOG_ARCHIVE}"
echo ""
echo "人工确认步骤:"
echo "  1. 验证登录: curl -X POST http://localhost:8000/api/v1/auth/login ..."
echo "  2. 验证聊天: 通过前端测试 RAG 问答"
echo "  3. 验证文档: 检查知识库文件完整性"
echo "  4. 检查日志: docker compose logs backend --tail=50"
echo "============================================"
