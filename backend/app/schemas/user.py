"""用户相关数据模型"""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field


class UserResponse(BaseModel):
    """用户安全响应 — 不包含 password_hash。"""

    id: int
    username: str
    display_name: str
    email: Optional[str] = None
    role: str
    is_active: bool
    is_superuser: bool
    last_login_at: Optional[str] = None
    created_at: str

    class Config:
        from_attributes = True
