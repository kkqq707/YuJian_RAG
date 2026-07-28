"""系统设置模型 — 可动态配置的系统参数

支持:
- 聊天设置（最大上下文长度、回答最大长度、历史保存天数）
- 知识库设置（Chunk Size、Chunk Overlap、Top K）
- 安全设置（JWT 有效期等）

安全:
- 敏感配置值加密存储
- 不通过 API 返回 JWT Secret 等敏感值
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, Integer, String, Text

from backend.app.models.base import Base


class SystemSetting(Base):
    """系统可配置设置项。

    非敏感配置: value 明文存储
    敏感配置: value 加密存储（type='encrypted'）
    """

    __tablename__ = "system_settings"

    id = Column(Integer, primary_key=True, autoincrement=True)
    key = Column(String(255), unique=True, nullable=False, index=True)
    value = Column(Text, nullable=False, default="")
    type = Column(String(50), nullable=False, default="string")
    description = Column(String(500), nullable=True, default="")
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
        return (
            f"SystemSetting(id={self.id}, key={self.key!r}, "
            f"type={self.type!r})"
        )
