"""管理员用户管理服务

提供:
- 用户列表查询
- 创建用户
- 禁用/启用用户
- 修改角色
- 重置密码
- 软删除用户

安全:
- 不返回 password_hash
- 不记录密码到日志
- 重置密码后撤销所有 Token
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from backend.app.models.user import User
from backend.app.repositories.token_repository import TokenRepository
from backend.app.repositories.user_repository import UserRepository
from backend.app.security.password import hash_password, validate_password_strength

logger = logging.getLogger(__name__)


class AdminUsersService:
    """管理员用户管理服务。"""

    def __init__(self, db: Session):
        self.db = db
        self.user_repo = UserRepository(db)
        self.token_repo = TokenRepository(db)

    # ------------------------------------------------------------------
    # 用户列表
    # ------------------------------------------------------------------

    def list_users(
        self,
        skip: int = 0,
        limit: int = 100,
        role: Optional[str] = None,
        is_active: Optional[bool] = None,
        search: Optional[str] = None,
    ) -> dict:
        """查询用户列表。

        Parameters
        ----------
        skip : int
            分页偏移
        limit : int
            每页数量
        role : str, optional
            按角色过滤
        is_active : bool, optional
            按激活状态过滤
        search : str, optional
            按用户名或显示名称搜索

        Returns
        -------
        dict
        """
        stmt = select(User)

        if role:
            stmt = stmt.where(User.role == role)
        if is_active is not None:
            stmt = stmt.where(User.is_active == is_active)
        if search:
            search_term = f"%{search.strip().lower()}%"
            from sqlalchemy import or_
            stmt = stmt.where(
                or_(
                    User.username.like(search_term),
                    User.display_name.like(search_term),
                )
            )

        # Count
        count_stmt = select(func.count()).select_from(stmt.subquery())
        total = self.db.execute(count_stmt).scalar_one()

        # Fetch
        stmt = stmt.order_by(User.created_at.desc()).offset(skip).limit(limit)
        users = list(self.db.execute(stmt).scalars().all())

        return {
            "success": True,
            "total": total,
            "users": self._serialize_users(users),
        }

    # ------------------------------------------------------------------
    # 创建用户
    # ------------------------------------------------------------------

    def create_user(
        self,
        username: str,
        password: str,
        display_name: str = "",
        email: Optional[str] = None,
        role: str = "user",
    ) -> dict:
        """创建新用户。

        Parameters
        ----------
        username : str
        password : str
        display_name : str
        email : str, optional
        role : str

        Returns
        -------
        dict

        Raises
        ------
        ValueError
            用户名已存在或密码强度不足
        """
        # 检查用户名唯一性
        existing = self.user_repo.get_by_username(username)
        if existing:
            raise ValueError(f"用户名 '{username}' 已被使用")

        # 检查邮箱唯一性
        if email:
            existing_email = self.user_repo.get_by_email(email)
            if existing_email:
                raise ValueError(f"邮箱 '{email}' 已被使用")

        # 验证密码强度
        valid, error_msg = validate_password_strength(password, username)
        if not valid:
            raise ValueError(error_msg or "密码强度不足")

        # 创建用户
        user = User(
            username=username.strip().lower(),
            display_name=display_name or username,
            email=email.strip().lower() if email else None,
            password_hash=hash_password(password),
            role=role,
            is_active=True,
            is_superuser=(role == "admin"),
        )
        self.user_repo.create(user)

        logger.info("管理员创建用户: %s (role=%s)", user.username, user.role)

        return {
            "success": True,
            "message": f"用户 '{user.username}' 创建成功",
            "user": self._serialize_user(user),
        }

    # ------------------------------------------------------------------
    # 更新用户基础信息
    # ------------------------------------------------------------------

    def update_user(
        self,
        user_id: int,
        display_name: Optional[str] = None,
        email: Optional[str] = None,
    ) -> dict:
        """更新用户基础信息（不允许修改 username、password、role）。

        Parameters
        ----------
        user_id : int
        display_name : str, optional
        email : str, optional

        Returns
        -------
        dict

        Raises
        ------
        ValueError
        """
        user = self._get_user_or_raise(user_id)

        if email is not None and email != user.email:
            # 检查邮箱唯一性
            existing = self.user_repo.get_by_email(email)
            if existing and existing.id != user_id:
                raise ValueError(f"邮箱 '{email}' 已被使用")
            user.email = email.strip().lower() if email else None

        if display_name is not None:
            user.display_name = display_name

        self.user_repo.update(user)
        logger.info("管理员更新用户信息: %s (id=%d)", user.username, user.id)

        return {
            "success": True,
            "message": f"用户 '{user.username}' 信息已更新",
            "user": self._serialize_user(user),
        }

    # ------------------------------------------------------------------
    # 禁用/启用用户
    # ------------------------------------------------------------------

    def set_user_active(self, user_id: int, active: bool) -> dict:
        """启用或禁用用户。

        Parameters
        ----------
        user_id : int
        active : bool

        Returns
        -------
        dict

        Raises
        ------
        ValueError
            用户不存在或操作不允许
        """
        user = self._get_user_or_raise(user_id)

        if user.is_active == active:
            state = "已启用" if active else "已禁用"
            raise ValueError(f"用户 {state}，无需重复操作")

        user.is_active = active
        self.user_repo.update(user)

        # 禁用时撤销所有 Token
        if not active:
            count = self.token_repo.revoke_all_for_user(user.id)
            logger.info("用户已禁用: %s, 已撤销 %d 个 Token", user.username, count)

        action_text = "启用" if active else "禁用"
        return {
            "success": True,
            "message": f"用户 '{user.username}' 已{action_text}",
            "user": self._serialize_user(user),
        }

    # ------------------------------------------------------------------
    # 修改角色
    # ------------------------------------------------------------------

    def change_role(self, user_id: int, new_role: str) -> dict:
        """修改用户角色。

        Parameters
        ----------
        user_id : int
        new_role : str

        Returns
        -------
        dict

        Raises
        ------
        ValueError
        """
        user = self._get_user_or_raise(user_id)

        if user.role == new_role:
            raise ValueError(f"用户角色已经是 '{new_role}'")

        old_role = user.role
        user.role = new_role
        user.is_superuser = (new_role == "admin")
        self.user_repo.update(user)

        # 角色变更后撤销所有 Token
        count = self.token_repo.revoke_all_for_user(user.id)
        logger.info(
            "用户角色变更: %s %s→%s, 已撤销 %d 个 Token",
            user.username, old_role, new_role, count,
        )

        return {
            "success": True,
            "message": f"用户 '{user.username}' 角色已从 '{old_role}' 变更为 '{new_role}'，所有设备需重新登录",
            "user": self._serialize_user(user),
        }

    # ------------------------------------------------------------------
    # 重置密码
    # ------------------------------------------------------------------

    def reset_password(self, user_id: int, new_password: str) -> dict:
        """重置用户密码（管理员操作）。

        Parameters
        ----------
        user_id : int
        new_password : str

        Returns
        -------
        dict

        Raises
        ------
        ValueError
        """
        user = self._get_user_or_raise(user_id)

        # 验证密码强度
        valid, error_msg = validate_password_strength(new_password, user.username)
        if not valid:
            raise ValueError(error_msg or "密码强度不足")

        # 更新密码
        user.password_hash = hash_password(new_password)
        user.password_changed_at = datetime.now(timezone.utc)
        self.user_repo.update(user)

        # 撤销所有 Token
        count = self.token_repo.revoke_all_for_user(user.id)
        logger.info(
            "管理员重置密码: %s, 已撤销 %d 个 Token", user.username, count,
        )

        return {
            "success": True,
            "message": f"用户 '{user.username}' 密码已重置，所有设备需重新登录",
        }

    # ------------------------------------------------------------------
    # 删除用户（软删除）
    # ------------------------------------------------------------------

    def delete_user(self, user_id: int) -> dict:
        """软删除用户。

        不允许删除自己。

        Parameters
        ----------
        user_id : int

        Returns
        -------
        dict

        Raises
        ------
        ValueError
        """
        user = self._get_user_or_raise(user_id)

        # 软删除
        user.is_active = False
        user.email = None  # 释放邮箱
        user.display_name = f"[已删除] {user.display_name}"
        self.user_repo.update(user)

        # 撤销所有 Token
        count = self.token_repo.revoke_all_for_user(user.id)
        logger.info(
            "管理员删除用户: %s (id=%d), 已撤销 %d 个 Token",
            user.username, user.id, count,
        )

        return {
            "success": True,
            "message": f"用户 '{user.username}' 已删除",
            "user_id": user.id,
        }

    # ------------------------------------------------------------------
    # 内部
    # ------------------------------------------------------------------

    def _get_user_or_raise(self, user_id: int) -> User:
        """按 ID 获取用户，不存在则抛异常。"""
        user = self.user_repo.get_by_id(user_id)
        if user is None:
            raise ValueError(f"用户不存在: id={user_id}")
        return user

    @staticmethod
    def _serialize_user(user: User) -> dict:
        """序列化用户为安全字典（不含 password_hash）。"""
        return {
            "id": user.id,
            "username": user.username,
            "display_name": user.display_name,
            "email": user.email,
            "role": user.role,
            "is_active": user.is_active,
            "is_superuser": user.is_superuser,
            "last_login_at": user.last_login_at.isoformat() if user.last_login_at else None,
            "created_at": user.created_at.isoformat() if user.created_at else None,
            "failed_login_attempts": user.failed_login_attempts,
            "locked_until": user.locked_until.isoformat() if user.locked_until else None,
        }

    @staticmethod
    def _serialize_users(users: list[User]) -> list[dict]:
        """批量序列化用户。"""
        return [AdminUsersService._serialize_user(u) for u in users]
