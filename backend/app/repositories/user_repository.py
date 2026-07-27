"""用户数据仓库

- 提供用户 CRUD 的数据访问层
- 不直接操作密码
- 不直接操作 Token
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.models.user import User


class UserRepository:
    """用户数据访问。"""

    def __init__(self, db: Session):
        self.db = db

    def get_by_id(self, user_id: int) -> User | None:
        """按 ID 查询用户。"""
        return self.db.get(User, user_id)

    def get_by_username(self, username: str) -> User | None:
        """按用户名查询（已标准化）。"""
        normalized = username.strip().lower()
        stmt = select(User).where(User.username == normalized)
        return self.db.execute(stmt).scalar_one_or_none()

    def get_by_email(self, email: str) -> User | None:
        """按邮箱查询（已标准化）。"""
        if not email:
            return None
        normalized = email.strip().lower()
        stmt = select(User).where(User.email == normalized)
        return self.db.execute(stmt).scalar_one_or_none()

    def create(self, user: User) -> User:
        """创建用户。"""
        self.db.add(user)
        self.db.flush()
        self.db.refresh(user)
        return user

    def update(self, user: User) -> User:
        """更新用户信息。"""
        user.updated_at = datetime.now(timezone.utc)
        self.db.flush()
        self.db.refresh(user)
        return user

    def record_login_success(self, user: User) -> User:
        """记录登录成功：清零失败次数，更新最后登录时间。"""
        user.failed_login_attempts = 0
        user.locked_until = None
        user.last_login_at = datetime.now(timezone.utc)
        self.db.flush()
        return user

    def record_login_failure(self, user: User, max_attempts: int, lock_minutes: int) -> User:
        """记录登录失败：递增失败次数，达到阈值后锁定。"""
        user.failed_login_attempts += 1
        if user.failed_login_attempts >= max_attempts:
            user.locked_until = datetime.now(timezone.utc) + timedelta(minutes=lock_minutes)
        self.db.flush()
        return user

    def count_active_superusers(self) -> int:
        """统计活跃超级管理员数量。"""
        stmt = select(User).where(
            User.is_active == True,
            User.is_superuser == True,
            User.role == "admin",
        )
        return len(self.db.execute(stmt).scalars().all())
