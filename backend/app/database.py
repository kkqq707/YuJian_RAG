"""数据库引擎与会话管理

Phase 7: SQLite 并发稳定性增强

- 使用 SQLAlchemy 2.0 风格
- SQLite 数据库路径: storage/app.db
- WAL 模式 + busy_timeout + 连接级 PRAGMA
- 请求级 Session 生命周期
- 启动日志输出数据库类型和超时配置（不输出敏感信息）
- 不影响未来 PostgreSQL DATABASE_URL
"""

from __future__ import annotations

import logging
from pathlib import Path

from sqlalchemy import create_engine, event, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from backend.app.config import get_settings

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# 数据库文件路径
# ---------------------------------------------------------------------------
settings = get_settings()

# 解析 sqlite:///storage/app.db -> 绝对路径
_db_url: str = settings.DATABASE_URL
if _db_url.startswith("sqlite:///"):
    _rel_path = _db_url[len("sqlite:///"):]
    _abs_path = str(settings.PROJECT_ROOT / _rel_path)
    DATABASE_URL = f"sqlite:///{_abs_path}"
else:
    DATABASE_URL = _db_url

# 检测数据库类型（用于条件逻辑，不在业务代码散落判断）
_IS_SQLITE = DATABASE_URL.startswith("sqlite")


def _is_sqlite() -> bool:
    """判断当前数据库是否为 SQLite（内部使用）。"""
    return _IS_SQLITE


# ---------------------------------------------------------------------------
# SQLite PRAGMA 事件监听
# ---------------------------------------------------------------------------


@event.listens_for(Engine, "connect")
def _set_sqlite_pragma(dbapi_connection, connection_record):
    """SQLite 连接时配置 PRAGMA。

    每个新连接都会执行以下 PRAGMA：
    - journal_mode=WAL: 读写并发提升
    - synchronous=NORMAL: WAL 模式下的安全折中
    - busy_timeout: 使用配置值，遇到锁时等待而非立即失败
    - foreign_keys=ON: 强制外键约束

    仅在 SQLite 连接下执行，不影响 PostgreSQL。
    """
    # 检测是否为 SQLite 连接（通过模块名判断，避免字符串匹配）
    dbapi_module = type(dbapi_connection).__module__
    if "sqlite" not in dbapi_module.lower():
        return

    cursor = dbapi_connection.cursor()
    try:
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA synchronous=NORMAL")
        busy_ms = settings.SQLITE_BUSY_TIMEOUT_MS
        cursor.execute(f"PRAGMA busy_timeout={int(busy_ms)}")
        cursor.execute("PRAGMA foreign_keys=ON")
    except Exception as e:
        logger.warning("SQLite PRAGMA 设置失败: %s", str(e)[:200])
    finally:
        cursor.close()


# ---------------------------------------------------------------------------
# 引擎
# ---------------------------------------------------------------------------

# SQLite 连接参数
connect_args: dict = {}
if _IS_SQLITE:
    connect_args = {
        "check_same_thread": False,
        "timeout": 30,  # sqlite3 模块级超时(秒)，作为 PRAGMA busy_timeout 的额外保障
    }

engine = create_engine(
    DATABASE_URL,
    echo=False,
    connect_args=connect_args,
    # SQLite 使用默认 SingletonThreadPool，不显式设置 poolclass
    # SingletonThreadPool 为每个线程维护一个连接，适合 FastAPI 的线程池模型
    # 不使用 StaticPool（仅适合内存 SQLite 测试），不使用 NullPool（会导致性能问题）
)

# 启动后验证 WAL 模式（仅在 SQLite 下验证）
if _IS_SQLITE:
    try:
        with engine.connect() as conn:
            result = conn.execute(text("PRAGMA journal_mode")).scalar()
            logger.info("数据库类型: SQLite | journal_mode: %s | busy_timeout: %dms",
                       result, settings.SQLITE_BUSY_TIMEOUT_MS)
    except Exception as e:
        logger.warning("启动时验证 SQLite journal_mode 失败: %s", str(e)[:200])
else:
    # 非 SQLite（未来 PostgreSQL 等）
    _db_type = "PostgreSQL" if "postgresql" in DATABASE_URL else "其他"
    logger.info("数据库类型: %s", _db_type)


# ---------------------------------------------------------------------------
# 会话工厂
# ---------------------------------------------------------------------------

SessionLocal = sessionmaker(
    bind=engine,
    autocommit=False,
    autoflush=False,
)


def get_db() -> Session:
    """FastAPI 依赖 — 获取数据库会话，请求成功时自动提交，结束后关闭。

    使用模式：
        @router.get("/path")
        async def handler(db: Session = Depends(get_db)):
            ...

    生命周期：
    - 请求开始：创建独立 Session
    - 请求成功：提交事务
    - 请求异常：回滚事务
    - 请求结束：关闭 Session（释放连接回池）

    警告：
    - 不在跨请求间共享 Session
    - 不将 Session 传入后台任务长期持有
    - 流式接口在开始 LLM 流之前完成必要读取并释放事务
    """
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def get_db_session() -> Session:
    """直接获取数据库会话（用于脚本、CLI、后台服务等非 FastAPI 上下文）。

    调用者负责关闭 Session 和事务管理。
    """
    return SessionLocal()


def get_db_type() -> str:
    """获取数据库类型字符串（供健康检查和管理接口使用）。"""
    url_lower = DATABASE_URL.lower()
    if url_lower.startswith("sqlite"):
        return "sqlite"
    if "postgresql" in url_lower:
        return "postgresql"
    if "mysql" in url_lower:
        return "mysql"
    return "unknown"
