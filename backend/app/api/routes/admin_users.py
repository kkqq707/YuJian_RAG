"""管理员用户管理路由

全部端点需要管理员权限 (require_admin)。

端点:
- GET    /api/v1/admin/users              — 用户列表
- POST   /api/v1/admin/users              — 创建用户
- PUT    /api/v1/admin/users/{id}/disable  — 禁用用户
- PUT    /api/v1/admin/users/{id}/enable   — 启用用户
- PUT    /api/v1/admin/users/{id}/role     — 修改角色
- POST   /api/v1/admin/users/{id}/reset-password — 重置密码
- DELETE /api/v1/admin/users/{id}          — 删除用户（软删除）
"""

from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.orm import Session

from backend.app.database import get_db
from backend.app.models.user import User
from backend.app.schemas.admin_users import (
    AdminUserItem,
    ChangeRoleRequest,
    ChangeRoleResponse,
    CreateUserRequest,
    CreateUserResponse,
    DeleteUserResponse,
    ResetPasswordRequest,
    ResetPasswordResponse,
    UpdateUserRequest,
    UserListResponse,
    UserStatusResponse,
)
from backend.app.security.dependencies import require_admin
from backend.app.services.admin_users_service import AdminUsersService
from backend.app.services.audit_service import AuditService

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/admin/users",
    tags=["管理员 - 用户管理"],
    dependencies=[Depends(require_admin)],
)


def _get_client_info(request: Request) -> tuple:
    """提取客户端信息用于审计日志。"""
    ip = request.client.host if request.client else None
    ua = request.headers.get("User-Agent")
    return ip, ua


# ---------------------------------------------------------------------------
# 用户列表
# ---------------------------------------------------------------------------


@router.get("", response_model=UserListResponse, summary="查看用户列表")
async def list_users(
    request: Request,
    skip: int = Query(0, ge=0, description="分页偏移"),
    limit: int = Query(100, ge=1, le=500, description="每页数量"),
    role: Optional[str] = Query(None, description="按角色过滤: admin | user"),
    is_active: Optional[bool] = Query(None, description="按激活状态过滤"),
    search: Optional[str] = Query(None, description="搜索用户名或显示名称"),
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """获取用户列表，支持分页、过滤和搜索。

    需要管理员权限。
    """
    service = AdminUsersService(db)
    result = service.list_users(
        skip=skip,
        limit=limit,
        role=role,
        is_active=is_active,
        search=search,
    )
    return UserListResponse(**result)


# ---------------------------------------------------------------------------
# 创建用户
# ---------------------------------------------------------------------------


@router.post("", response_model=CreateUserResponse, status_code=201, summary="创建用户")
async def create_user(
    request: Request,
    body: CreateUserRequest,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """创建新用户。

    需要管理员权限。
    密码至少 10 个字符，需包含字母和数字。
    """
    service = AdminUsersService(db)
    try:
        result = service.create_user(
            username=body.username,
            password=body.password,
            display_name=body.display_name,
            email=body.email,
            role=body.role,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    # 审计日志
    ip, ua = _get_client_info(request)
    audit = AuditService(db)
    audit.log(
        admin_user=current_user,
        action="user_create",
        target_type="user",
        target_id=str(result["user"]["id"]),
        detail=f"创建用户: username={body.username}, role={body.role}",
        ip_address=ip,
        user_agent=ua,
    )

    return CreateUserResponse(**result)


# ---------------------------------------------------------------------------
# 更新用户基础信息
# ---------------------------------------------------------------------------


@router.put("/{user_id}", response_model=UserStatusResponse, summary="更新用户基础信息")
async def update_user(
    request: Request,
    user_id: int,
    body: UpdateUserRequest,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """更新用户基础信息（显示名称、邮箱）。

    不允许修改 username、password、role。
    需要管理员权限。
    """
    service = AdminUsersService(db)
    try:
        result = service.update_user(
            user_id=user_id,
            display_name=body.display_name,
            email=body.email,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    # 审计日志
    ip, ua = _get_client_info(request)
    audit = AuditService(db)
    audit.log(
        admin_user=current_user,
        action="user_update",
        target_type="user",
        target_id=str(user_id),
        detail=f"更新用户信息: id={user_id}",
        ip_address=ip,
        user_agent=ua,
    )

    return UserStatusResponse(**result)


# ---------------------------------------------------------------------------
# 禁用用户
# ---------------------------------------------------------------------------


@router.put("/{user_id}/disable", response_model=UserStatusResponse, summary="禁用用户")
async def disable_user(
    request: Request,
    user_id: int,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """禁用指定用户。

    禁用后用户无法登录，所有 Token 被撤销。

    需要管理员权限。
    """
    if user_id == current_user.id:
        raise HTTPException(status_code=400, detail="不能禁用自己")

    service = AdminUsersService(db)
    try:
        result = service.set_user_active(user_id, active=False)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    # 审计日志
    ip, ua = _get_client_info(request)
    audit = AuditService(db)
    audit.log(
        admin_user=current_user,
        action="user_disable",
        target_type="user",
        target_id=str(user_id),
        detail=f"禁用用户: id={user_id}",
        ip_address=ip,
        user_agent=ua,
    )

    return UserStatusResponse(**result)


# ---------------------------------------------------------------------------
# 启用用户
# ---------------------------------------------------------------------------


@router.put("/{user_id}/enable", response_model=UserStatusResponse, summary="启用用户")
async def enable_user(
    request: Request,
    user_id: int,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """启用被禁用的用户。

    需要管理员权限。
    """
    service = AdminUsersService(db)
    try:
        result = service.set_user_active(user_id, active=True)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    # 审计日志
    ip, ua = _get_client_info(request)
    audit = AuditService(db)
    audit.log(
        admin_user=current_user,
        action="user_enable",
        target_type="user",
        target_id=str(user_id),
        detail=f"启用用户: id={user_id}",
        ip_address=ip,
        user_agent=ua,
    )

    return UserStatusResponse(**result)


# ---------------------------------------------------------------------------
# 修改角色
# ---------------------------------------------------------------------------


@router.put("/{user_id}/role", response_model=ChangeRoleResponse, summary="修改用户角色")
async def change_role(
    request: Request,
    user_id: int,
    body: ChangeRoleRequest,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """修改用户角色（admin / user）。

    角色变更后用户所有 Token 将被撤销，需重新登录。

    需要管理员权限。
    """
    if user_id == current_user.id:
        raise HTTPException(status_code=400, detail="不能修改自己的角色")

    service = AdminUsersService(db)
    try:
        result = service.change_role(user_id, body.role)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    # 审计日志
    ip, ua = _get_client_info(request)
    audit = AuditService(db)
    audit.log(
        admin_user=current_user,
        action="user_role_change",
        target_type="user",
        target_id=str(user_id),
        detail=f"修改角色: id={user_id}, new_role={body.role}",
        ip_address=ip,
        user_agent=ua,
    )

    return ChangeRoleResponse(**result)


# ---------------------------------------------------------------------------
# 重置密码
# ---------------------------------------------------------------------------


@router.post("/{user_id}/reset-password", response_model=ResetPasswordResponse, summary="重置用户密码")
async def reset_password(
    request: Request,
    user_id: int,
    body: ResetPasswordRequest,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """重置指定用户的密码。

    密码重置后所有 Token 将被撤销，用户需使用新密码重新登录。

    需要管理员权限。
    """
    service = AdminUsersService(db)
    try:
        result = service.reset_password(user_id, body.new_password)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    # 审计日志（不记录密码）
    ip, ua = _get_client_info(request)
    audit = AuditService(db)
    audit.log(
        admin_user=current_user,
        action="user_password_reset",
        target_type="user",
        target_id=str(user_id),
        detail=f"重置密码: id={user_id}",
        ip_address=ip,
        user_agent=ua,
    )

    return ResetPasswordResponse(**result)


# ---------------------------------------------------------------------------
# 删除用户
# ---------------------------------------------------------------------------


@router.delete("/{user_id}", response_model=DeleteUserResponse, summary="删除用户（软删除）")
async def delete_user(
    request: Request,
    user_id: int,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """软删除用户。

    不允许删除自己。
    删除后用户被禁用、邮箱被释放。

    需要管理员权限。
    """
    if user_id == current_user.id:
        raise HTTPException(status_code=400, detail="不能删除自己")

    service = AdminUsersService(db)
    try:
        result = service.delete_user(user_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    # 审计日志
    ip, ua = _get_client_info(request)
    audit = AuditService(db)
    audit.log(
        admin_user=current_user,
        action="user_delete",
        target_type="user",
        target_id=str(user_id),
        detail=f"删除用户: id={user_id}",
        ip_address=ip,
        user_agent=ua,
    )

    return DeleteUserResponse(**result)
