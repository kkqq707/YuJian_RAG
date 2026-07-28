"""后端配置 — 基于 pydantic-settings，复用项目根目录 .env

安全策略:
- 系统环境变量优先于 .env
- 不读取或暴露 API Key
- 配置 repr 不显示敏感字段
- JWT_SECRET_KEY 必须来自环境变量或 .env，无硬编码默认值
"""

from __future__ import annotations

import os
import secrets
from functools import lru_cache
from pathlib import Path

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


# ---------------------------------------------------------------------------
# 项目根目录 — 从 backend/app/config.py 向上两级到项目根
# ---------------------------------------------------------------------------
_PROJECT_ROOT: Path = Path(__file__).resolve().parent.parent.parent


class Settings(BaseSettings):
    """FastAPI 后端配置。

    字段名大小写不敏感，系统环境变量优先于 .env（override=False 效果）。
    """

    model_config = SettingsConfigDict(
        env_file=str(_PROJECT_ROOT / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # ---- 应用 ----
    APP_NAME: str = "企业智库 AI API"
    APP_VERSION: str = "0.1.0"
    APP_ENV: str = "development"
    DEBUG: bool = False

    # ---- 服务 ----
    API_PREFIX: str = "/api/v1"
    HOST: str = "127.0.0.1"
    PORT: int = 8000

    # ---- CORS — 生产环境不得默认允许 * ----
    CORS_ORIGINS: list[str] = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ]

    # ---- 数据库 ----
    DATABASE_URL: str = "sqlite:///storage/app.db"

    # ---- JWT ----
    JWT_SECRET_KEY: str = ""  # 必须来自环境变量或 .env，无硬编码默认值
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    JWT_ISSUER: str = "enterprise-knowledge-api"
    JWT_AUDIENCE: str = "enterprise-knowledge-client"

    # ---- 登录安全 ----
    MAX_LOGIN_ATTEMPTS: int = 5
    LOGIN_LOCK_MINUTES: int = 15

    # ---- 路径 ----
    @property
    def PROJECT_ROOT(self) -> Path:
        return _PROJECT_ROOT

    @property
    def DATA_DIR(self) -> Path:
        return _PROJECT_ROOT / "data"

    @property
    def STORAGE_DIR(self) -> Path:
        return _PROJECT_ROOT / "storage"

    # ---- 限制 ----
    MAX_QUESTION_LENGTH: int = 2000

    # ---- 推理并发控制 (Phase 6) ----
    EMBEDDING_MAX_CONCURRENCY: int = 2
    RERANKER_MAX_CONCURRENCY: int = 1
    INFERENCE_QUEUE_TIMEOUT_SECONDS: int = 30
    INFERENCE_TASK_TIMEOUT_SECONDS: int = 120
    INFERENCE_THREAD_POOL_SIZE: int = 2

    # ---- LLM HTTP 客户端 ----
    LLM_CONNECT_TIMEOUT_SECONDS: int = 10
    LLM_READ_TIMEOUT_SECONDS: int = 120
    LLM_WRITE_TIMEOUT_SECONDS: int = 30
    LLM_POOL_TIMEOUT_SECONDS: int = 10
    LLM_MAX_CONNECTIONS: int = 20
    LLM_MAX_KEEPALIVE_CONNECTIONS: int = 10

    # ---- 用户级并发 ----
    MAX_ACTIVE_RAG_REQUESTS_PER_USER: int = 1

    # ---- Uvicorn ----
    UVICORN_WORKERS: int = 1
    UVICORN_LIMIT_CONCURRENCY: int = 50
    UVICORN_BACKLOG: int = 128
    UVICORN_TIMEOUT_KEEP_ALIVE: int = 10

    # ---- 日志目录 ----
    @property
    def LOG_DIR(self) -> Path:
        return _PROJECT_ROOT / "storage" / "logs"

    # ---- 校验 ----

    @field_validator(
        "EMBEDDING_MAX_CONCURRENCY",
        "RERANKER_MAX_CONCURRENCY",
        "INFERENCE_THREAD_POOL_SIZE",
        "MAX_ACTIVE_RAG_REQUESTS_PER_USER",
        mode="after",
    )
    @classmethod
    def validate_positive_int(cls, v: int) -> int:
        """确保并发/线程池值 >= 1。"""
        if v < 1:
            raise ValueError(f"值必须 >= 1，当前值: {v}")
        return v

    @field_validator(
        "INFERENCE_QUEUE_TIMEOUT_SECONDS",
        "INFERENCE_TASK_TIMEOUT_SECONDS",
        "LLM_CONNECT_TIMEOUT_SECONDS",
        "LLM_READ_TIMEOUT_SECONDS",
        "LLM_WRITE_TIMEOUT_SECONDS",
        "LLM_POOL_TIMEOUT_SECONDS",
        mode="after",
    )
    @classmethod
    def validate_non_negative_timeout(cls, v: int) -> int:
        """确保超时值 >= 0。"""
        if v < 0:
            raise ValueError(f"超时值不得为负数，当前值: {v}")
        return v

    @field_validator("JWT_SECRET_KEY", mode="after")
    @classmethod
    def validate_jwt_secret(cls, v: str) -> str:
        """JWT_SECRET_KEY 验证。

        Phase 6D: JWT Secret 支持从数据库自动初始化。
        允许启动时为空（将从数据库 system_configs 表加载），
        但如果提供了值则必须长度 >= 32。
        """
        if not v:
            # Phase 6D: 允许为空，将在启动时从数据库自动初始化
            return v
        if len(v) < 32:
            raise ValueError(
                f"JWT_SECRET_KEY 长度不足（当前 {len(v)} 字节，要求至少 32 字节）。\n"
                "安全生成方法: python -c \"import secrets; print(secrets.token_urlsafe(48))\""
            )
        return v

    def __repr__(self) -> str:
        """安全 repr — 不显示 JWT_SECRET_KEY 等敏感字段。"""
        return (
            f"Settings(APP_NAME={self.APP_NAME!r}, APP_VERSION={self.APP_VERSION!r}, "
            f"APP_ENV={self.APP_ENV!r}, DEBUG={self.DEBUG!r}, "
            f"HOST={self.HOST!r}, PORT={self.PORT!r}, "
            f"JWT_ALGORITHM={self.JWT_ALGORITHM!r})"
        )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """获取缓存的 Settings 实例。

    lru_cache 确保整个进程生命周期内只创建一次配置对象。
    """
    return Settings()
