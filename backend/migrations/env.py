"""Alembic migration environment configuration.

Uses SQLAlchemy MetaData for auto-detection of model changes.
SQLite-compatible batch mode for ALTER operations.
"""

import logging
import os
import sys
import traceback
from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

logger = logging.getLogger("alembic.env")

# Add project root to sys.path so we can import backend.*
_PROJECT_ROOT = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..")
)
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

# Alembic Config object
config = context.config

# Logging
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Target metadata - auto-imported from models
from backend.app.models.base import Base  # noqa: E402
from backend.app.models.user import User  # noqa: E402, F401
from backend.app.models.refresh_token import RefreshToken  # noqa: E402, F401
from backend.app.models.system_config import SystemConfig  # noqa: E402, F401
from backend.app.models.llm_config import LLMConfig  # noqa: E402, F401
from backend.app.models.system_setting import SystemSetting  # noqa: E402, F401

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Offline migration - generate SQL script without connecting to DB."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Online migration - connect to database and execute."""
    try:
        connectable = engine_from_config(
            config.get_section(config.config_ini_section, {}),
            prefix="sqlalchemy.",
            poolclass=pool.NullPool,
        )
    except Exception as exc:
        logger.error("无法创建数据库引擎: %s", exc)
        logger.error("数据库 URL: %s", config.get_main_option("sqlalchemy.url", "(未设置)"))
        logger.error("请检查:\n"
                     "  1. SQLite 文件路径是否正确\n"
                     "  2. 存储卷是否可写（Windows Docker Desktop 下避免 bind mount）\n"
                     "  3. 磁盘空间是否充足")
        raise

    try:
        with connectable.connect() as connection:
            context.configure(
                connection=connection,
                target_metadata=target_metadata,
                render_as_batch=True,  # SQLite compatibility
            )

            with context.begin_transaction():
                context.run_migrations()
    except Exception as exc:
        logger.error("数据库迁移失败: %s", exc)
        logger.error("完整 traceback:\n%s", traceback.format_exc())
        raise


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
