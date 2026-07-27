"""用户服务

当前阶段（第 2 阶段）提供基础用户查询能力。
完整用户管理 CRUD 将在第 3 阶段实现。
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from backend.app.repositories.user_repository import UserRepository


class UserService:
    """用户服务。"""

    def __init__(self, db: Session):
        self.db = db
        self.user_repo = UserRepository(db)

    def get_by_id(self, user_id: int):
        """按 ID 查询用户。"""
        return self.user_repo.get_by_id(user_id)

    def get_by_username(self, username: str):
        """按用户名查询。"""
        return self.user_repo.get_by_username(username)
