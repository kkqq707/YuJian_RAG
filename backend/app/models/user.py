"""用户数据模型

- role 仅允许 "admin" / "user"
- password_hash 不得出现在 API 输出中（使用 response_model 排除）
- 用户名存储前做标准化
- 删除用户优先软删除（is_active=False）
- 创建时间使用 UTC
"""

from __future__ import annotations

import re
from datetime import datetime, timezone

from sqlalchemy import Boolean, Column, DateTime, Integer, String
from sqlalchemy.orm import validates

from backend.app.models.base import Base


# ---------------------------------------------------------------------------
# 允许的角色
# ---------------------------------------------------------------------------
VALID_ROLES = {"admin", "user"}


class User(Base):
    """系统用户。"""

    __tablename__ = "users"

    id = Column(Integer, primary_key=True, autoincrement=True)
    username = Column(String(150), unique=True, nullable=False, index=True)
    display_name = Column(String(255), nullable=False, default="")
    email = Column(String(320), unique=True, nullable=True, index=True)
    password_hash = Column(String(255), nullable=False)
    role = Column(String(20), nullable=False, default="user")
    is_active = Column(Boolean, nullable=False, default=True)
    is_superuser = Column(Boolean, nullable=False, default=False)
    failed_login_attempts = Column(Integer, nullable=False, default=0)
    locked_until = Column(DateTime(timezone=True), nullable=True)
    last_login_at = Column(DateTime(timezone=True), nullable=True)
    password_changed_at = Column(DateTime(timezone=True), nullable=True)
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

    # ------------------------------------------------------------------
    # 校验
    # ------------------------------------------------------------------

    @validates("username")
    def _normalize_username(self, key: str, value: str) -> str:
        """标准化用户名：去除首尾空白，统一小写。"""
        if value is None:
            raise ValueError("用户名不能为空")
        cleaned = value.strip().lower()
        if not cleaned:
            raise ValueError("用户名不能为空")
        if len(cleaned) > 150:
            raise ValueError("用户名不能超过 150 个字符")
        if not re.match(r'^[a-z0-9_\-\.]+$', cleaned):
            raise ValueError("用户名只能包含字母、数字、下划线、连字符和点")
        return cleaned

    @validates("email")
    def _normalize_email(self, key: str, value: str | None) -> str | None:
        """标准化邮箱：去除首尾空白，统一小写。"""
        if value is None:
            return None
        cleaned = value.strip().lower()
        if not cleaned:
            return None
        if len(cleaned) > 320:
            raise ValueError("邮箱不能超过 320 个字符")
        return cleaned

    @validates("role")
    def _validate_role(self, key: str, value: str) -> str:
        """验证角色只能是 admin 或 user。"""
        if value not in VALID_ROLES:
            raise ValueError(f"无效的角色: {value}，允许的角色: {', '.join(sorted(VALID_ROLES))}")
        return value

    # ------------------------------------------------------------------
    # 辅助属性
    # ------------------------------------------------------------------

    @property
    def is_locked(self) -> bool:
        """检查账户是否被临时锁定。"""
        if self.locked_until is None:
            return False
        now = datetime.now(timezone.utc)
        lock = self.locked_until
        # SQLite may return naive datetime — normalize to UTC
        if lock.tzinfo is None:
            lock = lock.replace(tzinfo=timezone.utc)
        return now < lock

    def __repr__(self) -> str:
        """安全 repr — 不包含 password_hash。"""
        return (
            f"User(id={self.id}, username={self.username!r}, "
            f"role={self.role!r}, is_active={self.is_active})"
        )
