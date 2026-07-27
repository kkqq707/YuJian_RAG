"""认证依赖注入

提供:
- get_current_user(): 从 Bearer Token 获取当前用户
- get_current_active_user(): 获取当前活跃用户
- require_admin(): 要求管理员权限
- require_role(*roles): 要求特定角色

规则:
1. 缺少 Token 返回 401
2. 无效或过期 Token 返回 401
3. 用户已禁用返回 403
4. 角色不足返回 403
5. 返回头包含合理的 WWW-Authenticate
6. 每次敏感请求都重新确认用户状态
7. 不能只相信 Token 中的 role，必须检查数据库当前状态
8. 管理员被降级后，旧 Token 不能继续访问管理员接口
"""

from __future__ import annotations

import logging
from typing import List

from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jwt.exceptions import InvalidTokenError
from sqlalchemy.orm import Session

from backend.app.database import get_db
from backend.app.models.user import User
from backend.app.security.jwt import verify_access_token

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Bearer Token 方案
# ---------------------------------------------------------------------------
security_scheme = HTTPBearer(
    scheme_name="JWT",
    description="输入 Access Token: Bearer <token>",
    auto_error=False,
)


# ---------------------------------------------------------------------------
# 依赖
# ---------------------------------------------------------------------------


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(security_scheme),
    db: Session = Depends(get_db),
) -> User:
    """从请求中提取并验证当前用户。

    每次请求都重新从数据库加载用户状态，不只信任 Token 中的信息。
    """
    if credentials is None:
        raise HTTPException(
            status_code=401,
            detail="需要登录才能访问",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = credentials.credentials

    try:
        payload = verify_access_token(token)
    except InvalidTokenError:
        raise HTTPException(
            status_code=401,
            detail="Token 无效或已过期",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user_id = int(payload.get("sub", 0))
    token_role = payload.get("role")

    # 每次请求重新确认用户状态
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(
            status_code=401,
            detail="用户不存在",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.is_active:
        raise HTTPException(
            status_code=403,
            detail="账户已被禁用",
        )

    # 验证角色未被更改（管理员被降级 → 旧 Token 无效）
    if user.role != token_role:
        raise HTTPException(
            status_code=403,
            detail="用户权限已变更，请重新登录",
        )

    return user


async def get_current_active_user(
    current_user: User = Depends(get_current_user),
) -> User:
    """获取当前活跃用户（is_active=True）。"""
    return current_user


def require_admin(
    current_user: User = Depends(get_current_active_user),
) -> User:
    """要求管理员权限。普通用户返回 403。"""
    if current_user.role != "admin":
        raise HTTPException(
            status_code=403,
            detail="需要管理员权限",
        )
    return current_user


def require_role(*roles: str):
    """要求特定角色（工厂函数）。

    Usage:
        @router.get("/admin/something")
        async def admin_only(user = Depends(require_role("admin"))):
            ...
    """

    def _check_role(
        current_user: User = Depends(get_current_active_user),
    ) -> User:
        if current_user.role not in roles:
            allowed = ", ".join(roles)
            raise HTTPException(
                status_code=403,
                detail=f"需要以下角色之一: {allowed}",
            )
        return current_user

    return _check_role
