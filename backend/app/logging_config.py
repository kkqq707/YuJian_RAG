"""日志配置 — 统一日志格式，安全过滤敏感信息

- 不记录 API Key
- 不记录 Authorization 头
- 不记录完整问题答案正文
- 可记录请求路径、状态码、耗时、问题长度、refused 状态
"""

from __future__ import annotations

import logging
import logging.config
import os
import sys
from pathlib import Path

from backend.app.config import get_settings


# ---------------------------------------------------------------------------
# 自定义 Formatter — 安全处理缺失的字段
# ---------------------------------------------------------------------------


class SafeFormatter(logging.Formatter):
    """格式化器，为缺失的 request_id 字段提供默认值 '-'。"""

    def format(self, record: logging.LogRecord) -> str:
        if not hasattr(record, "request_id"):
            record.request_id = "-"
        return super().format(record)


# ---------------------------------------------------------------------------
# 日志过滤器 — 过滤敏感字段
# ---------------------------------------------------------------------------


class SensitiveDataFilter(logging.Filter):
    """过滤日志记录中的 API Key 和 Authorization 头。"""

    _SENSITIVE_PATTERNS = [
        "api_key",
        "authorization",
        "bearer",
        "deepseek_api_key",
        "openai_api_key",
        "dashscope_api_key",
    ]

    def filter(self, record: logging.LogRecord) -> bool:
        """始终允许日志记录通过，但修改消息内容模糊化敏感信息。"""
        if hasattr(record, "msg") and isinstance(record.msg, str):
            msg_lower = record.msg.lower()
            for pattern in self._SENSITIVE_PATTERNS:
                if pattern in msg_lower:
                    record.msg = "[FILTERED: message contained sensitive data]"
        return True


# ---------------------------------------------------------------------------
# 日志初始化
# ---------------------------------------------------------------------------


def setup_logging() -> None:
    """配置应用日志。

    - DEBUG=false 时日志级别为 INFO，否则为 DEBUG
    - 控制台 + 文件双输出
    - 日志文件写入 storage/logs/
    """
    settings = get_settings()
    log_level = "DEBUG" if settings.DEBUG else "INFO"

    # 确保日志目录存在
    log_dir = settings.LOG_DIR
    log_dir.mkdir(parents=True, exist_ok=True)

    config = {
        "version": 1,
        "disable_existing_loggers": False,
        "filters": {
            "sensitive": {
                "()": "backend.app.logging_config.SensitiveDataFilter",
            },
        },
        "formatters": {
            "default": {
                "()": "backend.app.logging_config.SafeFormatter",
                "format": (
                    "%(asctime)s | %(levelname)-8s | "
                    "%(name)s | %(request_id)s | "
                    "%(message)s"
                ),
                "datefmt": "%Y-%m-%d %H:%M:%S",
            },
            "access": {
                "()": "backend.app.logging_config.SafeFormatter",
                "format": (
                    "%(asctime)s | %(levelname)-8s | "
                    "ACCESS | %(request_id)s | "
                    "%(message)s"
                ),
                "datefmt": "%Y-%m-%d %H:%M:%S",
            },
        },
        "handlers": {
            "console": {
                "class": "logging.StreamHandler",
                "stream": sys.stdout,
                "formatter": "default",
                "filters": ["sensitive"],
                "level": log_level,
            },
            "file": {
                "class": "logging.handlers.RotatingFileHandler",
                "filename": str(log_dir / "backend.log"),
                "maxBytes": 10 * 1024 * 1024,  # 10 MB
                "backupCount": 5,
                "formatter": "default",
                "filters": ["sensitive"],
                "level": log_level,
                "encoding": "utf-8",
            },
        },
        "loggers": {
            "": {
                "handlers": ["console", "file"],
                "level": "WARNING",
            },
            "src": {
                "handlers": ["console", "file"],
                "level": log_level,
                "propagate": False,
            },
            "backend": {
                "handlers": ["console", "file"],
                "level": log_level,
                "propagate": False,
            },
            "uvicorn": {
                "handlers": ["console", "file"],
                "level": "INFO",
                "propagate": False,
            },
            "uvicorn.access": {
                "handlers": ["console", "file"],
                "level": "WARNING",
                "propagate": False,
            },
        },
    }

    logging.config.dictConfig(config)


def get_logger(name: str) -> logging.Logger:
    """获取日志记录器，确保日志系统已初始化。"""
    return logging.getLogger(name)
