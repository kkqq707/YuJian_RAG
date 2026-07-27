"""数据库引擎与会话管理

- 使用 SQLAlchemy 2.0 风格
- SQLite 数据库路径: storage/app.db
- 不与现有 knowledge_metadata.db 混用
- 连接参数针对 SQLite 优化
"""

from __future__ import annotations

import logging
from pathlib import Path

from sqlalchemy import create_engine, event
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

# ---------------------------------------------------------------------------
# 引擎
# ---------------------------------------------------------------------------


@event.listens_for(Engine, "connect")
def _set_sqlite_pragma(dbapi_connection, connection_record):
    """SQLite 连接时启用 WAL 模式和外键约束。"""
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


engine = create_engine(
    DATABASE_URL,
    echo=False,
    connect_args={"check_same_thread": False} if "sqlite" in DATABASE_URL else {},
)

# ---------------------------------------------------------------------------
# 会话工厂
# ---------------------------------------------------------------------------

SessionLocal = sessionmaker(
    bind=engine,
    autocommit=False,
    autoflush=False,
)


def get_db() -> Session:
    """FastAPI 依赖 — 获取数据库会话，请求成功时自动提交，结束后关闭。"""
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
    """直接获取数据库会话（用于脚本、CLI 等非 FastAPI 上下文）。"""
    return SessionLocal()
