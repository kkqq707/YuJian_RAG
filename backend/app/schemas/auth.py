"""认证相关数据模型 — 请求与响应

安全要求:
- password 不出现在响应中
- password_hash 不出现在任何输出模型中
- Token 不出现在 URL 查询参数
"""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# 请求
# ---------------------------------------------------------------------------


class LoginRequest(BaseModel):
    """登录请求。"""

    username: str = Field(..., description="用户名", min_length=1, max_length=150)
    password: str = Field(..., description="密码", min_length=1)


class RefreshRequest(BaseModel):
    """刷新 Token 请求。"""

    refresh_token: str = Field(..., description="Refresh Token", min_length=1)


class ChangePasswordRequest(BaseModel):
    """修改密码请求。"""

    old_password: str = Field(..., description="当前密码", min_length=1)
    new_password: str = Field(..., description="新密码", min_length=1)


# ---------------------------------------------------------------------------
# 响应
# ---------------------------------------------------------------------------


class UserInfo(BaseModel):
    """安全用户信息 — 不包含 password_hash。"""

    id: int = Field(..., description="用户 ID")
    username: str = Field(..., description="用户名")
    display_name: str = Field("", description="显示名称")
    role: str = Field(..., description="角色")


class TokenResponse(BaseModel):
    """Token 响应。"""

    access_token: str = Field(..., description="Access Token")
    refresh_token: str = Field(..., description="Refresh Token")
    token_type: str = Field("bearer", description="Token 类型")
    expires_in: int = Field(..., description="Access Token 过期时间（秒）")
    user: UserInfo = Field(..., description="用户信息")
    must_change_password: bool = Field(False, description="是否必须修改密码（首次登录/默认密码）")


class RefreshResponse(BaseModel):
    """刷新 Token 响应。"""

    access_token: str = Field(..., description="新 Access Token")
    refresh_token: str = Field(..., description="新 Refresh Token")
    token_type: str = Field("bearer", description="Token 类型")
    expires_in: int = Field(..., description="Access Token 过期时间（秒）")


class MessageResponse(BaseModel):
    """通用消息响应。"""

    success: bool = Field(True, description="操作是否成功")
    message: str = Field(..., description="消息描述")
