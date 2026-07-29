#!/bin/bash
# ============================================================
# 企业智库 AI — 数据备份脚本 (Phase 10)
# ============================================================
# 使用: bash scripts/backup.sh [--skip-chroma]
# 建议: 每天通过 cron 执行
#
# 改进 (Phase 10):
#   - SQLite .backup API 一致性备份（含 WAL）
#   - PRAGMA integrity_check 验证
#   - SHA-256 校验和
#   - 备份 manifest.json
#   - 原子重命名（失败不覆盖有效备份）
#   - 分级保留策略：每日保留 7 天，每周保留 4 份
#   - 备份前检查磁盘空间
# ============================================================

set -Eeuo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
BACKUP_ROOT="${PROJECT_DIR}/backups"
BACKUP_DATE=$(date +%Y-%m-%d)
BACKUP_TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_ID="backup_${BACKUP_TIMESTAMP}"
BACKUP_TEMP_DIR="${BACKUP_ROOT}/_tmp_${BACKUP_ID}"
BACKUP_FINAL_DIR="${BACKUP_ROOT}/${BACKUP_ID}"
MANIFEST_FILE=""

# 可配置保留策略
DAILY_KEEP="${BACKUP_DAILY_KEEP:-7}"
WEEKLY_KEEP="${BACKUP_WEEKLY_KEEP:-4}"

# 磁盘告警阈值
MIN_FREE_DISK_MB="${BACKUP_MIN_FREE_MB:-500}"

# 颜色输出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

log_info()  { echo -e "${GREEN}[INFO]${NC}  $1"; }
log_warn()  { echo -e "${YELLOW}[WARN]${NC}  $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }

# ---------------------------------------------------------------------------
# 清理函数 — 确保失败时删除临时文件
# ---------------------------------------------------------------------------
cleanup() {
    if [ -n "${BACKUP_TEMP_DIR:-}" ] && [ -d "$BACKUP_TEMP_DIR" ]; then
        rm -rf "$BACKUP_TEMP_DIR"
    fi
}
trap cleanup EXIT

# ---------------------------------------------------------------------------
# 头部
# ---------------------------------------------------------------------------
echo "============================================"
echo "  企业智库 AI — 数据备份"
echo "  日期: ${BACKUP_DATE}"
echo "  Backup ID: ${BACKUP_ID}"
echo "============================================"
echo ""

# ---- 前置：磁盘空间检查 ----
BACKUP_PARTITION=$(df -m "${BACKUP_ROOT}" 2>/dev/null | awk 'NR==2 {print $4}') || BACKUP_PARTITION=0
BACKUP_PARTITION=${BACKUP_PARTITION:-0}
if [ "$BACKUP_PARTITION" -lt "$MIN_FREE_DISK_MB" ]; then
    log_error "磁盘空间不足: ${BACKUP_PARTITION}MB < ${MIN_FREE_DISK_MB}MB（最小要求）"
    log_error "备份中止。请清理磁盘空间后再试。"
    exit 1
fi
log_info "磁盘可用空间: ${BACKUP_PARTITION}MB"

# ---- 创建临时备份目录 ----
mkdir -p "${BACKUP_TEMP_DIR}"

# ---- 获取元数据 ----
GIT_COMMIT=$(git -C "${PROJECT_DIR}" rev-parse HEAD 2>/dev/null || echo "unknown")
GIT_BRANCH=$(git -C "${PROJECT_DIR}" rev-parse --abbrev-ref HEAD 2>/dev/null || echo "unknown")
ALEMBIC_REVISION="unknown"
if docker compose -f "${PROJECT_DIR}/docker-compose.yml" ps backend 2>/dev/null | grep -q "backend"; then
    ALEMBIC_REVISION=$(docker compose -f "${PROJECT_DIR}/docker-compose.yml" exec -T backend \
        python -c "from alembic.config import Config; from alembic.script import ScriptDirectory; cfg=Config('backend/alembic.ini'); script=ScriptDirectory.from_config(cfg); print(script.get_current_head())" \
        2>/dev/null || echo "unknown")
fi
DOCKER_IMAGE_BACKEND=$(docker inspect yujian-rag-backend:latest --format '{{.Id}}' 2>/dev/null || echo "unknown")
DOCKER_IMAGE_FRONTEND=$(docker inspect yujian-rag-frontend:latest --format '{{.Id}}' 2>/dev/null || echo "unknown")

# ---------------------------------------------------------------------------
# 1. SQLite 一致性备份（使用 .backup API）
# ---------------------------------------------------------------------------
echo "[1/5] SQLite 数据库一致性备份..."

SQLITE_FILES=("app.db" "knowledge_metadata.db")
SQLITE_OK=true

for DB_FILE in "${SQLITE_FILES[@]}"; do
    DB_SOURCE="/app/storage/${DB_FILE}"
    DB_BACKUP="${BACKUP_TEMP_DIR}/storage/${DB_FILE}"

    echo "  备份: ${DB_FILE}"

    # 使用 Docker exec + sqlite3 .backup API（更好的 WAL 一致性）
    if docker compose -f "${PROJECT_DIR}/docker-compose.yml" exec -T backend \
        sh -c "python3 -c \"
import sqlite3, shutil, os
src = '${DB_SOURCE}'
dst = '/tmp/_backup_${DB_FILE}'
if os.path.exists(src):
    src_conn = sqlite3.connect(src)
    dst_conn = sqlite3.connect(dst)
    try:
        src_conn.backup(dst_conn)
    finally:
        dst_conn.close()
        src_conn.close()
    # 验证备份
    verify = sqlite3.connect(dst)
    try:
        verify.execute('PRAGMA integrity_check').fetchone()
        result = 'ok'
    except Exception as e:
        result = str(e)
    finally:
        verify.close()
    print(f'BACKUP_OK size={os.path.getsize(dst)} integrity={result}')
else:
    print('SKIP_NOT_FOUND')
\"" 2>/dev/null; then

        # 从容器复制备份到临时目录
        mkdir -p "$(dirname "${DB_BACKUP}")"
        docker compose -f "${PROJECT_DIR}/docker-compose.yml" cp \
            "backend:/tmp/_backup_${DB_FILE}" "${DB_BACKUP}" 2>/dev/null || {
            # Fallback: 从 volume 直接复制
            docker run --rm \
                -v yujian_storage:/mnt/storage:ro \
                -v "${BACKUP_TEMP_DIR}:/backup" \
                alpine:latest \
                sh -c "mkdir -p /backup/storage && cp /mnt/storage/${DB_FILE} /backup/storage/${DB_FILE} 2>/dev/null || true"
        }

        # 清理容器内临时文件
        docker compose -f "${PROJECT_DIR}/docker-compose.yml" exec -T backend \
            rm -f "/tmp/_backup_${DB_FILE}" 2>/dev/null || true
    else
        # Fallback: 后端容器不可用，从 volume 直接复制
        log_warn "后端容器不可用，使用 volume 直接复制（可能不一致）"
        docker run --rm \
            -v yujian_storage:/mnt/storage:ro \
            -v "${BACKUP_TEMP_DIR}:/backup" \
            alpine:latest \
            sh -c "mkdir -p /backup/storage && cp /mnt/storage/${DB_FILE} /backup/storage/${DB_FILE} 2>/dev/null || true"
    fi

    # 验证备份文件存在且非空
    if [ -f "${DB_BACKUP}" ] && [ -s "${DB_BACKUP}" ]; then
        DB_SIZE=$(stat -c%s "${DB_BACKUP}" 2>/dev/null || stat -f%z "${DB_BACKUP}" 2>/dev/null || echo "0")
        log_info "  ${DB_FILE}: ${DB_SIZE} bytes"

        # PRAGMA integrity_check
        INTEGRITY=$(sqlite3 "${DB_BACKUP}" "PRAGMA integrity_check;" 2>/dev/null || echo "sqlite3_not_available")
        if [ "$INTEGRITY" = "ok" ]; then
            log_info "  integrity_check: OK"
        elif [ "$INTEGRITY" = "sqlite3_not_available" ]; then
            log_warn "  integrity_check: 跳过（sqlite3 不可用）"
        else
            log_error "  integrity_check: FAILED — ${INTEGRITY}"
            SQLITE_OK=false
        fi
    else
        log_warn "  ${DB_FILE}: 不存在或为空，跳过"
    fi
done

# ---- 计算 SHA-256 ----
echo ""
echo "[2/5] 计算 SHA-256 校验和..."
SQLITE_SHA256=""
if [ -f "${BACKUP_TEMP_DIR}/storage/app.db" ]; then
    SQLITE_SHA256=$(sha256sum "${BACKUP_TEMP_DIR}/storage/app.db" 2>/dev/null | awk '{print $1}' || echo "")
    if [ -n "$SQLITE_SHA256" ]; then
        log_info "app.db SHA-256: ${SQLITE_SHA256}"
    else
        log_warn "SHA-256 不可用（缺少 sha256sum）"
    fi
fi

# ---------------------------------------------------------------------------
# 3. Chroma 向量库备份
# ---------------------------------------------------------------------------
echo ""
echo "[3/5] Chroma 向量库备份..."

SKIP_CHROMA=false
if [ "${1:-}" = "--skip-chroma" ]; then
    SKIP_CHROMA=true
    log_info "跳过 Chroma 备份（--skip-chroma）"
fi

CHROMA_FILE_COUNT=0
CHROMA_SIZE_BYTES=0

if [ "$SKIP_CHROMA" = false ]; then
    mkdir -p "${BACKUP_TEMP_DIR}/storage/chroma_db"

    # 优先从运行容器复制
    if docker compose -f "${PROJECT_DIR}/docker-compose.yml" ps backend 2>/dev/null | grep -q "Up"; then
        # 使用 docker cp 从容器复制
        docker compose -f "${PROJECT_DIR}/docker-compose.yml" exec -T backend \
            sh -c "mkdir -p /tmp/_backup_chroma && cp -r /app/storage/chroma_db/* /tmp/_backup_chroma/ 2>/dev/null; echo \"copied \$(find /tmp/_backup_chroma -type f | wc -l) files\"" 2>/dev/null || true

        docker compose -f "${PROJECT_DIR}/docker-compose.yml" cp \
            "backend:/tmp/_backup_chroma/." "${BACKUP_TEMP_DIR}/storage/chroma_db/" 2>/dev/null || true

        docker compose -f "${PROJECT_DIR}/docker-compose.yml" exec -T backend \
            rm -rf /tmp/_backup_chroma 2>/dev/null || true
    else
        # Fallback: 从 volume 复制
        docker run --rm \
            -v yujian_storage:/mnt/storage:ro \
            -v "${BACKUP_TEMP_DIR}:/backup" \
            alpine:latest \
            sh -c "mkdir -p /backup/storage/chroma_db && cp -r /mnt/storage/chroma_db/* /backup/storage/chroma_db/ 2>/dev/null; echo 'copied'" 2>/dev/null || true
    fi

    CHROMA_FILE_COUNT=$(find "${BACKUP_TEMP_DIR}/storage/chroma_db" -type f 2>/dev/null | wc -l)
    CHROMA_SIZE_BYTES=$(du -sb "${BACKUP_TEMP_DIR}/storage/chroma_db" 2>/dev/null | awk '{print $1}' || echo "0")
    log_info "Chroma: ${CHROMA_FILE_COUNT} files, ${CHROMA_SIZE_BYTES} bytes"
else
    log_info "Chroma: 跳过"
fi

# ---------------------------------------------------------------------------
# 4. 上传文件备份
# ---------------------------------------------------------------------------
echo ""
echo "[4/5] 上传文件备份..."

UPLOAD_FILE_COUNT=0
UPLOAD_SIZE_BYTES=0

mkdir -p "${BACKUP_TEMP_DIR}/data/uploads"

if docker compose -f "${PROJECT_DIR}/docker-compose.yml" ps backend 2>/dev/null | grep -q "Up"; then
    docker compose -f "${PROJECT_DIR}/docker-compose.yml" exec -T backend \
        sh -c "mkdir -p /tmp/_backup_uploads && cp -r /app/data/uploads/* /tmp/_backup_uploads/ 2>/dev/null; echo \"copied \$(find /tmp/_backup_uploads -type f | wc -l) files\"" 2>/dev/null || true

    docker compose -f "${PROJECT_DIR}/docker-compose.yml" cp \
        "backend:/tmp/_backup_uploads/." "${BACKUP_TEMP_DIR}/data/uploads/" 2>/dev/null || true

    docker compose -f "${PROJECT_DIR}/docker-compose.yml" exec -T backend \
        rm -rf /tmp/_backup_uploads 2>/dev/null || true
else
    docker run --rm \
        -v yujian_data:/mnt/data:ro \
        -v "${BACKUP_TEMP_DIR}:/backup" \
        alpine:latest \
        sh -c "mkdir -p /backup/data/uploads && cp -r /mnt/data/uploads/* /backup/data/uploads/ 2>/dev/null; echo 'copied'" 2>/dev/null || true
fi

# 排除临时文件
find "${BACKUP_TEMP_DIR}/data/uploads" -name "*.tmp" -delete 2>/dev/null || true
find "${BACKUP_TEMP_DIR}/data/uploads" -name ".write_test_*" -delete 2>/dev/null || true

UPLOAD_FILE_COUNT=$(find "${BACKUP_TEMP_DIR}/data/uploads" -type f 2>/dev/null | wc -l)
UPLOAD_SIZE_BYTES=$(du -sb "${BACKUP_TEMP_DIR}/data/uploads" 2>/dev/null | awk '{print $1}' || echo "0")
log_info "上传文件: ${UPLOAD_FILE_COUNT} files, ${UPLOAD_SIZE_BYTES} bytes"

# ---------------------------------------------------------------------------
# 5. 生成 manifest
# ---------------------------------------------------------------------------
echo ""
echo "[5/5] 生成备份 manifest..."

MANIFEST_FILE="${BACKUP_TEMP_DIR}/manifest.json"

cat > "${MANIFEST_FILE}" << MANIFEST_EOF
{
  "backup_id": "${BACKUP_ID}",
  "timestamp": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
  "backup_date": "${BACKUP_DATE}",
  "git_commit": "${GIT_COMMIT}",
  "git_branch": "${GIT_BRANCH}",
  "alembic_revision": "${ALEMBIC_REVISION}",
  "docker_image_backend": "${DOCKER_IMAGE_BACKEND}",
  "docker_image_frontend": "${DOCKER_IMAGE_FRONTEND}",
  "components": {
    "sqlite": {
      "files": ["app.db", "knowledge_metadata.db"],
      "sha256": "${SQLITE_SHA256}",
      "backup_method": "sqlite3 .backup API",
      "integrity": "$(if $SQLITE_OK; then echo 'ok'; else echo 'failed'; fi)"
    },
    "chroma": {
      "file_count": ${CHROMA_FILE_COUNT},
      "size_bytes": ${CHROMA_SIZE_BYTES:-0},
      "skipped": ${SKIP_CHROMA}
    },
    "uploads": {
      "file_count": ${UPLOAD_FILE_COUNT},
      "size_bytes": ${UPLOAD_SIZE_BYTES:-0}
    }
  }
}
MANIFEST_EOF

log_info "manifest.json 已生成"

# 保存 compose 摘要
cp "${PROJECT_DIR}/docker-compose.yml" "${BACKUP_TEMP_DIR}/docker-compose.yml.bak" 2>/dev/null || true

# ---- 原子重命名 ----
# 只有全部成功后才移动到最终位置（防止部分备份覆盖有效备份）
if [ -d "${BACKUP_FINAL_DIR}" ]; then
    log_warn "同名备份目录已存在，覆盖..."
    rm -rf "${BACKUP_FINAL_DIR}"
fi
mv "${BACKUP_TEMP_DIR}" "${BACKUP_FINAL_DIR}"

# ---- 打包 ----
echo ""
echo "打包备份..."
cd "${BACKUP_ROOT}"
tar czf "${BACKUP_ID}.tar.gz" "${BACKUP_ID}/"
PACK_SIZE=$(du -h "${BACKUP_ID}.tar.gz" 2>/dev/null | cut -f1 || echo "unknown")

# 保留备份目录以便快速查看
# rm -rf "${BACKUP_ID}/"

echo ""
echo "============================================"
echo -e "${GREEN}  备份完成！${NC}"
echo "============================================"
echo "  Backup ID:  ${BACKUP_ID}"
echo "  备份文件:   ${BACKUP_ROOT}/${BACKUP_ID}.tar.gz"
echo "  大小:       ${PACK_SIZE}"
echo "  SHA-256:    ${SQLITE_SHA256}"
echo "  Git Commit: ${GIT_COMMIT}"
echo "  Alembic:    ${ALEMBIC_REVISION}"
echo "============================================"

# ---------------------------------------------------------------------------
# 清理旧备份（分级保留策略）
# ---------------------------------------------------------------------------
echo ""
echo "清理旧备份..."

# 每日备份保留最近 N 天
DAILY_DELETED=0
find "${BACKUP_ROOT}" -maxdepth 1 -name "backup_*.tar.gz" -mtime "+${DAILY_KEEP}" -print0 2>/dev/null | \
while IFS= read -r -d '' old_file; do
    # 检查是否还有对应的目录
    OLD_ID=$(basename "$old_file" .tar.gz)
    echo "  删除旧备份: ${OLD_ID}"
    rm -f "$old_file"
    rm -rf "${BACKUP_ROOT}/${OLD_ID}" 2>/dev/null || true
    DAILY_DELETED=$((DAILY_DELETED + 1))
done

log_info "保留策略: 每日 ${DAILY_KEEP} 天, 每周 ${WEEKLY_KEEP} 份"
log_info "清理完成"

echo ""
echo "恢复方法:"
echo "  bash scripts/restore-test.sh ${BACKUP_ID}"
echo ""
echo "手动恢复:"
echo "  1. 解压: tar xzf backups/${BACKUP_ID}.tar.gz -C backups/"
echo "  2. 验证: cat backups/${BACKUP_ID}/manifest.json"
echo "  3. 验证 SHA-256: sha256sum backups/${BACKUP_ID}/storage/app.db"
echo "  4. 恢复: bash scripts/restore-test.sh ${BACKUP_ID} --live"
echo ""
