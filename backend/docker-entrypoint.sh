#!/bin/bash
# ============================================================
# 企业智库 AI — Backend 容器启动脚本
# 1. 检查 SQLite 存储卷可写性
# 2. 运行数据库迁移
# 3. 初始化管理员账户
# 4. 启动 FastAPI 服务
# ============================================================

set -e

echo "============================================"
echo "  企业智库 AI Backend — 容器启动"
echo "============================================"
echo ""
echo "PYTHONPATH: ${PYTHONPATH:-/app}"
echo "Working Dir: $(pwd)"
echo ""

# ---- 1. 确保运行时目录存在 ----
mkdir -p /app/storage/logs /app/storage/backup /app/storage/chroma_db /app/data/uploads

# ---- 2. 检查 SQLite 存储卷可写性 ----
echo "[0/3] 检查 SQLite 存储卷可写性..."
SQLITE_DB_PATH="/app/storage/app.db"
SQLITE_DB_DIR=$(dirname "$SQLITE_DB_PATH")

# 检查目录是否存在且可写
if [ ! -d "$SQLITE_DB_DIR" ]; then
    echo "  [ERROR] 存储目录不存在: $SQLITE_DB_DIR"
    exit 1
fi

if [ ! -w "$SQLITE_DB_DIR" ]; then
    echo "  [ERROR] 存储目录不可写: $SQLITE_DB_DIR"
    echo "  请检查 Docker volume 是否正确挂载。"
    exit 1
fi

# 尝试创建/写入 SQLite 文件验证磁盘 I/O 正常
SQLITE_TEST_FILE="${SQLITE_DB_DIR}/.write_test_$(date +%s)"
if ! touch "$SQLITE_TEST_FILE" 2>/dev/null; then
    echo "  [ERROR] SQLite 存储卷写入测试失败（disk I/O error）"
    echo "  这通常是由于 Windows Docker Desktop 下使用 bind mount 导致。"
    echo "  请确保 docker-compose.yml 中使用 named volume 而非 bind mount。"
    exit 1
fi
rm -f "$SQLITE_TEST_FILE"

# 如果数据库文件已存在，验证其可读写
if [ -f "$SQLITE_DB_PATH" ]; then
    if [ ! -r "$SQLITE_DB_PATH" ] || [ ! -w "$SQLITE_DB_PATH" ]; then
        echo "  [ERROR] SQLite 数据库文件不可读写: $SQLITE_DB_PATH"
        exit 1
    fi
    echo "  [OK] SQLite 数据库文件可读写: $SQLITE_DB_PATH"
else
    echo "  [OK] SQLite 存储卷可写，数据库文件将在迁移时创建"
fi
echo ""

# ---- 3. 数据库迁移（含异常日志） ----
echo "[1/3] 运行数据库迁移..."
cd /app/backend

MIGRATION_LOG="/app/storage/logs/migration_$(date +%Y%m%d_%H%M%S).log"
echo "  迁移日志: $MIGRATION_LOG"

set +e  # 暂时禁用 errexit，捕获迁移错误
python -m alembic -c alembic.ini upgrade head 2>&1 | tee "$MIGRATION_LOG"
MIGRATION_EXIT_CODE=${PIPESTATUS[0]}
set -e

if [ $MIGRATION_EXIT_CODE -ne 0 ]; then
    echo ""
    echo "  =========================================="
    echo "  [FATAL] 数据库迁移失败！"
    echo "  =========================================="
    echo "  退出码: $MIGRATION_EXIT_CODE"
    echo "  完整日志: $MIGRATION_LOG"
    echo ""
    echo "  常见原因:"
    echo "  1. SQLite disk I/O error — Windows Docker Desktop bind mount 问题"
    echo "     → 确保 docker-compose.yml 使用 named volume: yujian_storage:/app/storage"
    echo "  2. 数据库文件损坏"
    echo "     → 删除 storage/app.db 后重建容器"
    echo "  3. 迁移脚本冲突"
    echo "     → 检查日志中的 Python traceback"
    echo ""
    echo "  最后 20 行日志:"
    echo "  -----------------------------------------"
    tail -20 "$MIGRATION_LOG" 2>/dev/null || true
    echo "  -----------------------------------------"
    exit 1
fi

echo "  迁移完成"
echo ""

# ---- 4. 初始化管理员账户 ----
echo "[2/3] 初始化管理员账户..."
cd /app
python -c "
import os, sys, logging
sys.path.insert(0, '/app')

logging.basicConfig(level=logging.WARNING)

from backend.app.database import SessionLocal, engine
from backend.app.models.base import Base
from backend.app.models.user import User
from backend.app.security.password import hash_password, verify_password

# 确保表存在
Base.metadata.create_all(bind=engine)

# ---- 安全的密码哈希生成（内部已有异常保护） ----
def safe_hash_password(pw: str) -> str:
    try:
        return hash_password(pw)
    except Exception as e:
        print(f'  [FATAL] hash_password() 失败: {e}')
        import traceback
        traceback.print_exc()
        raise

# 默认管理员密码（标准化以确保不超过 72 字节）
DEFAULT_PASSWORD = 'admin123456'

db = SessionLocal()
try:
    existing = db.query(User).filter(User.username == 'admin').first()
    if existing:
        print(f'  管理员已存在: admin (role={existing.role})')
        needs_fix = False

        # 检查现有密码哈希是否有效（是否为正确的 bcrypt 哈希）
        hash_str = existing.password_hash or ''
        if not hash_str.startswith('\$2'):
            print('  [WARN] 管理员密码哈希格式异常，重新生成')
            needs_fix = True
        else:
            # 验证默认密码是否能通过验证
            try:
                if not verify_password(DEFAULT_PASSWORD, existing.password_hash):
                    print('  [WARN] 管理员默认密码验证失败，重新生成哈希')
                    needs_fix = True
                else:
                    print('  [OK] 管理员密码哈希有效')
            except Exception:
                print('  [WARN] 管理员密码哈希验证过程中异常，重新生成')
                needs_fix = True

        if needs_fix:
            existing.password_hash = safe_hash_password(DEFAULT_PASSWORD)
            existing.password_changed_at = None  # 重置为首次登录状态
            existing.failed_login_attempts = 0
            existing.locked_until = None
            db.commit()
            print('  [OK] 管理员密码哈希已修复为默认密码 admin123456')
    else:
        user = User(
            username='admin',
            display_name='系统管理员',
            email=None,
            password_hash=safe_hash_password(DEFAULT_PASSWORD),
            role='admin',
            is_superuser=True,
            is_active=True,
            # password_changed_at=None → 首次登录强制修改密码
        )
        db.add(user)
        db.commit()
        print('  [OK] 管理员账户已创建: admin / admin123456')
        print('  [WARN] 首次登录强制修改密码！password_changed_at=None')
        print('  [WARN] 登录后 API 返回 must_change_password=true，前端将引导修改密码')
except Exception as e:
    db.rollback()
    import traceback
    print(f'  [FATAL] 管理员初始化失败: {e}')
    traceback.print_exc()
    # 不退出 — 管理员初始化失败不应阻止容器启动
    # （可能是权限问题，后续可手动修复）
finally:
    db.close()
"
echo ""

# ---- 5. 启动 FastAPI ----
echo "[3/3] 启动 FastAPI 服务..."
echo ""
exec uvicorn backend.app.main:app --host 0.0.0.0 --port 8000
