"""LLM 配置数据模型 — 企业 AI 模型服务配置

支持多个 LLM 提供商配置，同一时间只有一个启用 (enabled=true)。

安全策略:
- api_key_encrypted 始终为密文
- 禁止在日志/API 中暴露 API Key 明文
- 数据库查询不返回 api_key_encrypted 给非管理员
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import Boolean, Column, DateTime, Integer, String, Text

from backend.app.models.base import Base


class LLMConfig(Base):
    """LLM 模型配置。

    每个配置代表一个 AI 模型服务商（如 DeepSeek、OpenAI 等）。
    使用 OpenAI-compatible API 格式。
    """

    __tablename__ = "llm_configs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    provider = Column(
        String(100), nullable=False, default="openai-compatible",
        doc="服务商标识: openai-compatible / deepseek / openai / dashscope"
    )
    base_url = Column(
        String(500), nullable=False, default="",
        doc="API Base URL，例如 https://api.deepseek.com/v1"
    )
    api_key_encrypted = Column(
        Text, nullable=False, default="",
        doc="加密后的 API Key"
    )
    model = Column(
        String(200), nullable=False, default="",
        doc="模型名称，例如 deepseek-chat"
    )
    enabled = Column(
        Boolean, nullable=False, default=True,
        doc="是否启用（同一时间仅一个启用）"
    )
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    def __repr__(self) -> str:
        """安全 repr — 不显示 api_key_encrypted。"""
        return (
            f"LLMConfig(id={self.id}, provider={self.provider!r}, "
            f"model={self.model!r}, enabled={self.enabled})"
        )
