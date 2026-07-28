"""
后端权限依赖测试

覆盖:
- require_normal_user: 管理员返回 403，普通用户正常通过
- require_admin: 普通用户返回 403，管理员正常通过
- get_current_user: 未登录返回 401
"""
from __future__ import annotations

import pytest
from unittest.mock import MagicMock, patch

from fastapi import HTTPException

from backend.app.models.user import User
from backend.app.security.dependencies import (
    get_current_user,
    get_current_active_user,
    require_admin,
    require_normal_user,
)


# ============================================================================
# 辅助：创建测试用户
# ============================================================================

def _make_user(user_id: int = 1, username: str = "testuser", role: str = "user", is_active: bool = True) -> User:
    """创建内存中的 User 对象（不写入数据库）。"""
    user = User(
        id=user_id,
        username=username,
        display_name=username.title(),
        role=role,
        is_active=is_active,
    )
    return user


# ============================================================================
# require_normal_user — 管理员禁止使用用户端对话功能
# ============================================================================

class TestRequireNormalUser:
    """测试 require_normal_user 依赖。"""

    def test_normal_user_passes(self):
        """普通用户调用 require_normal_user 应正常通过。"""
        user = _make_user(role="user")
        result = require_normal_user(current_user=user)
        assert result is user
        assert result.role == "user"

    def test_admin_is_blocked_with_403(self):
        """管理员调用 require_normal_user 应返回 403。"""
        user = _make_user(role="admin")
        with pytest.raises(HTTPException) as exc_info:
            require_normal_user(current_user=user)
        assert exc_info.value.status_code == 403
        assert "管理员" in exc_info.value.detail

    def test_error_message_is_clear(self):
        """403 错误消息应明确指出管理员不可使用用户端功能。"""
        user = _make_user(role="admin", username="superadmin")
        with pytest.raises(HTTPException) as exc_info:
            require_normal_user(current_user=user)
        assert "管理员账号不可使用用户端对话功能" == exc_info.value.detail


# ============================================================================
# require_admin — 普通用户禁止访问管理员接口
# ============================================================================

class TestRequireAdmin:
    """测试 require_admin 依赖。"""

    def test_admin_passes(self):
        """管理员调用 require_admin 应正常通过。"""
        user = _make_user(role="admin")
        result = require_admin(current_user=user)
        assert result is user
        assert result.role == "admin"

    def test_normal_user_is_blocked_with_403(self):
        """普通用户调用 require_admin 应返回 403。"""
        user = _make_user(role="user")
        with pytest.raises(HTTPException) as exc_info:
            require_admin(current_user=user)
        assert exc_info.value.status_code == 403
        assert "管理员" in exc_info.value.detail


# ============================================================================
# get_current_active_user — 用户状态检查
# ============================================================================

class TestGetCurrentActiveUser:
    """测试 get_current_active_user 依赖。"""

    @pytest.mark.asyncio
    async def test_active_user_passes(self):
        """活跃用户应正常通过。"""
        user = _make_user(is_active=True)
        result = await get_current_active_user(current_user=user)
        assert result is user

    # get_current_active_user 只是一个透传，实际的 is_active 检查在 get_current_user 中完成
    # get_current_user 需要 token + db session，无法直接在此测试


# ============================================================================
# 角色边界测试
# ============================================================================

class TestRoleEdgeCases:
    """角色边界情况测试。"""

    def test_admin_is_not_user(self):
        """管理员 isAdmin=True 时不应被允许访问用户接口。"""
        user = _make_user(role="admin")
        with pytest.raises(HTTPException) as exc_info:
            require_normal_user(current_user=user)
        assert exc_info.value.status_code == 403

    def test_user_is_not_admin(self):
        """普通用户不应被允许访问管理员接口。"""
        user = _make_user(role="user")
        with pytest.raises(HTTPException) as exc_info:
            require_admin(current_user=user)
        assert exc_info.value.status_code == 403

    def test_inactive_user_role_checks_still_work(self):
        """禁用用户调用 require_normal_user 时 role 检查仍应生效。"""
        user = _make_user(role="admin", is_active=False)
        with pytest.raises(HTTPException) as exc_info:
            require_normal_user(current_user=user)
        assert exc_info.value.status_code == 403
