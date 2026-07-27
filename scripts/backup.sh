#!/bin/bash
# ============================================================
# 企业智库 AI — 数据备份脚本
# ============================================================
# 使用: bash scripts/backup.sh
# 建议: 每天通过 cron / 计划任务执行
#
# 备份内容:
#   1. SQLite 数据库 (app.db + knowledge_metadata.db)
#   2. Chroma 向量库 (chroma.sqlite3 + collection data)
#   3. 上传文件 (uploads)
#   4. 系统配置 / 日志
#
# 备份目标: ./backups/YYYY-MM-DD/
# 保留策略: 保留最近 7 天备份
# ============================================================

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
BACKUP_ROOT="${PROJECT_DIR}/backups"
BACKUP_DATE=$(date +%Y-%m-%d)
BACKUP_DIR="${BACKUP_ROOT}/${BACKUP_DATE}"

echo "============================================"
echo "  企业智库 AI — 数据备份"
echo "  日期: ${BACKUP_DATE}"
echo "============================================"
echo ""

# ---- 创建备份目录 ----
mkdir -p "${BACKUP_DIR}"

# ---- 1. 备份数据库（从 named volume） ----
echo "[1/4] 备份数据库..."
docker run --rm \
    -v yujian_storage:/mnt/storage:ro \
    -v "${BACKUP_DIR}:/backup" \
    alpine:latest \
    sh -c "cp /mnt/storage/app.db /backup/app.db 2>/dev/null; \
           cp /mnt/storage/knowledge_metadata.db /backup/knowledge_metadata.db 2>/dev/null; \
           echo '  数据库备份完成'"

# ---- 2. 备份 Chroma 向量库 ----
echo "[2/4] 备份 Chroma 向量库..."
docker run --rm \
    -v yujian_storage:/mnt/storage:ro \
    -v "${BACKUP_DIR}:/backup" \
    alpine:latest \
    sh -c "mkdir -p /backup/chroma_db; \
           cp -r /mnt/storage/chroma_db/* /backup/chroma_db/ 2>/dev/null; \
           echo '  Chroma 备份完成'"

# ---- 3. 备份上传文件 ----
echo "[3/4] 备份上传文件..."
docker run --rm \
    -v yujian_data:/mnt/data:ro \
    -v "${BACKUP_DIR}:/backup" \
    alpine:latest \
    sh -c "mkdir -p /backup/uploads; \
           cp -r /mnt/data/uploads/* /backup/uploads/ 2>/dev/null; \
           echo '  上传文件备份完成'"

# ---- 4. 备份配置和日志 ----
echo "[4/4] 备份配置和日志..."
docker run --rm \
    -v yujian_storage:/mnt/storage:ro \
    -v "${BACKUP_DIR}:/backup" \
    alpine:latest \
    sh -c "mkdir -p /backup/logs; \
           cp -r /mnt/storage/logs/* /backup/logs/ 2>/dev/null; \
           echo '  日志备份完成'"

# 复制 compose 和 env 配置
cp "${PROJECT_DIR}/docker-compose.yml" "${BACKUP_DIR}/" 2>/dev/null || true
cp "${PROJECT_DIR}/.env.production" "${BACKUP_DIR}/" 2>/dev/null || true

# ---- 打包备份 ----
echo ""
echo "打包备份..."
cd "${BACKUP_ROOT}"
tar czf "${BACKUP_DATE}.tar.gz" "${BACKUP_DATE}/"
rm -rf "${BACKUP_DATE}/"
echo "  备份文件: ${BACKUP_ROOT}/${BACKUP_DATE}.tar.gz"
echo "  大小: $(du -h "${BACKUP_DATE}.tar.gz" 2>/dev/null | cut -f1 || echo 'unknown')"

# ---- 清理旧备份（保留最近 7 天） ----
echo ""
echo "清理旧备份（保留最近 7 天）..."
find "${BACKUP_ROOT}" -name "*.tar.gz" -mtime +7 -delete 2>/dev/null || true
echo "  清理完成"

echo ""
echo "============================================"
echo "  备份完成！"
echo "  备份文件: ${BACKUP_ROOT}/${BACKUP_DATE}.tar.gz"
echo "============================================"
echo ""
echo "恢复方法:"
echo "  1. 解压: tar xzf backups/${BACKUP_DATE}.tar.gz -C backups/restore/"
echo "  2. 停止服务: docker compose stop"
echo "  3. 创建临时容器恢复:"
echo "     docker run --rm -v yujian_storage:/mnt/storage -v \$(pwd)/backups/restore/${BACKUP_DATE}:/restore alpine sh -c 'cp /restore/app.db /mnt/storage/'"
echo "  4. 启动服务: docker compose up -d"
