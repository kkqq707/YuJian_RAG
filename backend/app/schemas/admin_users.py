"""管理员用户管理 — 请求与响应模型"""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator


# ---------------------------------------------------------------------------
# 用户列表
# ---------------------------------------------------------------------------


class AdminUserItem(BaseModel):
    """管理员视角的用户条目（含 email、状态等管理字段）。"""

    id: int = Field(..., description="用户 ID")
    username: str = Field(..., description="用户名")
    display_name: str = Field("", description="显示名称")
    email: Optional[str] = Field(None, description="邮箱")
    role: str = Field(..., description="角色: admin | user")
    is_active: bool = Field(..., description="是否启用")
    is_superuser: bool = Field(False, description="是否超级管理员")
    last_login_at: Optional[str] = Field(None, description="最后登录时间")
    created_at: Optional[str] = Field(None, description="创建时间")
    failed_login_attempts: int = Field(0, description="登录失败次数")
    locked_until: Optional[str] = Field(None, description="锁定到期时间")

    model_config = ConfigDict(from_attributes=True)


class UserListResponse(BaseModel):
    """用户列表响应。"""

    success: bool = Field(True, description="请求是否成功")
    total: int = Field(..., description="用户总数")
    users: list[AdminUserItem] = Field(default_factory=list, description="用户列表")


# ---------------------------------------------------------------------------
# 创建用户
# ---------------------------------------------------------------------------


class CreateUserRequest(BaseModel):
    """创建用户请求。"""

    username: str = Field(
        ...,
        description="用户名",
        min_length=1,
        max_length=150,
        examples=["newuser"],
    )
    password: str = Field(
        ...,
        description="密码（至少 10 个字符，含字母和数字）",
        min_length=10,
        examples=["SecurePass123"],
    )
    display_name: str = Field("", description="显示名称", max_length=255)
    email: Optional[str] = Field(None, description="邮箱", max_length=320)
    role: str = Field("user", description="角色: admin | user")

    @field_validator("role")
    @classmethod
    def validate_role(cls, v: str) -> str:
        if v not in ("admin", "user"):
            raise ValueError("角色只能是 admin 或 user")
        return v


class CreateUserResponse(BaseModel):
    """创建用户响应。"""

    success: bool = Field(True, description="操作是否成功")
    message: str = Field(..., description="结果描述")
    user: AdminUserItem = Field(..., description="创建的用户信息")


# ---------------------------------------------------------------------------
# 修改角色
# ---------------------------------------------------------------------------


class ChangeRoleRequest(BaseModel):
    """修改角色请求。"""

    role: str = Field(..., description="新角色: admin | user")

    @field_validator("role")
    @classmethod
    def validate_role(cls, v: str) -> str:
        if v not in ("admin", "user"):
            raise ValueError("角色只能是 admin 或 user")
        return v


class ChangeRoleResponse(BaseModel):
    """修改角色响应。"""

    success: bool = Field(True, description="操作是否成功")
    message: str = Field(..., description="结果描述")
    user: AdminUserItem = Field(..., description="更新后的用户信息")


# ---------------------------------------------------------------------------
# 重置密码
# ---------------------------------------------------------------------------


class ResetPasswordRequest(BaseModel):
    """重置密码请求。"""

    new_password: str = Field(
        ...,
        description="新密码（至少 10 个字符，含字母和数字）",
        min_length=10,
        examples=["NewSecurePass456"],
    )


class ResetPasswordResponse(BaseModel):
    """重置密码响应。"""

    success: bool = Field(True, description="操作是否成功")
    message: str = Field(..., description="结果描述")


# ---------------------------------------------------------------------------
# 状态变更
# ---------------------------------------------------------------------------


class UserStatusResponse(BaseModel):
    """用户状态变更响应。"""

    success: bool = Field(True, description="操作是否成功")
    message: str = Field(..., description="结果描述")
    user: AdminUserItem = Field(..., description="更新后的用户信息")


# ---------------------------------------------------------------------------
# 删除用户
# ---------------------------------------------------------------------------


class DeleteUserResponse(BaseModel):
    """删除用户响应。"""

    success: bool = Field(True, description="操作是否成功")
    message: str = Field(..., description="结果描述")
    user_id: int = Field(..., description="被删除的用户 ID")


# ---------------------------------------------------------------------------
# 更新用户基础信息
# ---------------------------------------------------------------------------


class UpdateUserRequest(BaseModel):
    """更新用户基础信息请求 — 不允许修改 username、password、role。"""

    display_name: Optional[str] = Field(None, description="显示名称", max_length=255)
    email: Optional[str] = Field(None, description="邮箱", max_length=320)
