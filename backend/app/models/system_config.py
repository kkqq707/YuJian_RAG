"""系统配置数据模型 — 企业级配置存储

保存 JWT Secret、LLM 配置等敏感企业级配置。
所有敏感值必须加密存储，禁止明文入库。

安全策略:
- config_value_encrypted 始终为密文
- 禁止在日志/API 中暴露解密后的值
- JWT Secret 不可通过 API 返回
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, Integer, String, Text

from backend.app.models.base import Base


class SystemConfig(Base):
    """企业级系统配置。

    用于存储 jwt_secret_key 等全局配置。
    敏感值使用 AES 加密后存入 config_value_encrypted。
    """

    __tablename__ = "system_configs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    config_key = Column(String(255), unique=True, nullable=False, index=True)
    config_value_encrypted = Column(Text, nullable=False)
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
        """安全 repr — 不显示加密后的值。"""
        return (
            f"SystemConfig(id={self.id}, config_key={self.config_key!r}, "
            f"description={self.description!r})"
        )
