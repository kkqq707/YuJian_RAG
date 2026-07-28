"""Refresh Token 数据模型

- 数据库不保存完整 Refresh Token 明文
- 保存 Token 的安全哈希（SHA-256）
- 每个 Refresh Token 有唯一 jti
- 支持撤销（revoked_at）
- 支持按用户/设备撤销
- Access Token 不需要存库
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import relationship

from backend.app.models.base import Base


class RefreshToken(Base):
    """Refresh Token 记录。"""

    __tablename__ = "refresh_tokens"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    token_jti = Column(String(36), unique=True, nullable=False, index=True)
    token_hash = Column(String(64), nullable=False, index=True)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    revoked_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
    created_ip = Column(String(45), nullable=True)
    user_agent = Column(String(512), nullable=True)

    # 关联
    user = relationship("User", backref="refresh_tokens", lazy="select")

    @property
    def is_revoked(self) -> bool:
        return self.revoked_at is not None

    @property
    def is_expired(self) -> bool:
        if self.expires_at is None:
            return True
        now = datetime.now(timezone.utc)
        # SQLite may return naive datetime — normalize to UTC
        exp = self.expires_at
        if exp.tzinfo is None:
            exp = exp.replace(tzinfo=timezone.utc)
        return now > exp

    @property
    def is_valid(self) -> bool:
        return not self.is_revoked and not self.is_expired

    def revoke(self) -> None:
        """撤销此 Token。"""
        self.revoked_at = datetime.now(timezone.utc)

    def __repr__(self) -> str:
        return (
            f"RefreshToken(id={self.id}, user_id={self.user_id}, "
            f"jti={self.token_jti[:8]}..., valid={self.is_valid})"
        )
