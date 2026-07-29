"""认证路由 — 登录、刷新、退出、当前用户、修改密码

所有密码和 Token 相关接口:
- 密码不在响应中返回
- Token 不在响应头中暴露
- 错误统一使用安全消息
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from backend.app.config import get_settings
from backend.app.database import get_db
from backend.app.models.user import User
from backend.app.schemas.auth import (
    ChangePasswordRequest,
    LoginRequest,
    MessageResponse,
    RefreshRequest,
    RefreshResponse,
    TokenResponse,
    UserInfo,
)
from backend.app.security.dependencies import get_current_active_user
from backend.app.services.auth_service import AuthService, AuthenticationError
from backend.app.services.audit_service import AuditService
from backend.app.rate_limiter import check_rate_limit
from backend.app.client_ip import get_client_ip

logger = logging.getLogger(__name__)

router = APIRouter(tags=["认证"])


# ---------------------------------------------------------------------------
# 辅助：获取客户端 IP 和 User-Agent
# ---------------------------------------------------------------------------


def _get_client_info(request: Request) -> tuple[str | None, str | None]:
    """安全提取客户端 IP 和 User-Agent。"""
    ip = request.client.host if request.client else None
    ua = request.headers.get("User-Agent")
    return ip, ua


# ---------------------------------------------------------------------------
# 公开端点
# ---------------------------------------------------------------------------


@router.post("/auth/login")
async def login(request: Request, body: LoginRequest, db: Session = Depends(get_db)):
    """用户登录 — 返回 Access Token 和 Refresh Token。

    安全:
    - 用户不存在/密码错误统一返回 401
    - 锁定提示不泄露用户是否存在
    - 不在日志中记录密码
    - 任何意外异常安全降级为 401（绝不返回 500）
    """
    ip, ua = _get_client_info(request)

    # Phase 9: 限流检查
    client_ip, _ = get_client_ip(request)
    check_rate_limit(client_ip, "auth_login")

    try:
        auth_service = AuthService(db)
        result = auth_service.authenticate(body.username, body.password, ip, ua)

        # 记录登录成功审计日志
        try:
            from sqlalchemy import select as sa_select2
            stmt = sa_select2(User).where(User.id == result["user"]["id"])
            login_user = db.execute(stmt).scalar_one_or_none()
            if login_user:
                audit = AuditService(db)
                audit.log(
                    admin_user=login_user,
                    action="login_success",
                    target_type="auth",
                    detail=f"登录成功: role={result['user']['role']}",
                    ip_address=ip,
                    user_agent=ua,
                    status="success",
                )
        except Exception:
            pass

        logger.info(
            "用户登录成功 | username=%s | role=%s",
            result["user"]["username"],
            result["user"]["role"],
        )
        return result

    except AuthenticationError as e:
        # 记录登录失败审计日志
        try:
            from sqlalchemy import select as sa_select
            stmt = sa_select(User).where(User.username == body.username)
            found_user = db.execute(stmt).scalar_one_or_none()
            if found_user:
                audit = AuditService(db)
                audit.log(
                    admin_user=found_user,
                    action="login_failed",
                    target_type="auth",
                    detail=f"登录失败: {e.message}",
                    ip_address=ip,
                    user_agent=ua,
                    status="failed",
                )
        except Exception:
            pass
        raise HTTPException(status_code=e.status_code, detail=e.message)

    except HTTPException:
        # 已经是 HTTPException，直接重新抛出
        raise

    except Exception:
        # 任何意外异常安全降级为 401 — 绝不返回 500
        logger.exception(
            "login critical error username=%s",
            body.username,
        )
        raise HTTPException(status_code=401, detail="用户名或密码错误")


@router.post("/auth/refresh", response_model=RefreshResponse)
async def refresh_token(
    request: Request, body: RefreshRequest, db: Session = Depends(get_db)
):
    """刷新 Access Token — 使用 Refresh Token 换取新 Token 对。

    一次轮换策略:
    - 旧 Refresh Token 被撤销
    - 检测到已撤销 Token 再次使用 → 撤销该用户所有 Token
    """
    ip, ua = _get_client_info(request)

    # Phase 9: 限流检查
    client_ip, _ = get_client_ip(request)
    check_rate_limit(client_ip, "auth_refresh")

    auth_service = AuthService(db)

    try:
        result = auth_service.refresh_access_token(body.refresh_token, ip, ua)
    except AuthenticationError as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)

    logger.info("Token 刷新成功 | user_id=%d", result["user"]["id"])
    return result


# ---------------------------------------------------------------------------
# 需登录端点
# ---------------------------------------------------------------------------


@router.post("/auth/logout", response_model=MessageResponse)
async def logout(
    request: Request,
    body: RefreshRequest,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """退出登录 — 撤销当前 Refresh Token。"""
    ip, ua = _get_client_info(request)
    auth_service = AuthService(db)
    auth_service.logout(body.refresh_token)

    # 审计日志
    try:
        audit = AuditService(db)
        audit.log(
            admin_user=current_user,
            action="logout",
            target_type="auth",
            detail="用户退出登录",
            ip_address=ip,
            user_agent=ua,
            status="success",
        )
    except Exception:
        pass

    logger.info("用户退出登录 | user_id=%d", current_user.id)
    return MessageResponse(success=True, message="已退出登录")


@router.post("/auth/logout-all", response_model=MessageResponse)
async def logout_all(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """退出所有设备 — 撤销当前用户全部 Refresh Token。"""
    auth_service = AuthService(db)
    count = auth_service.logout_all(current_user.id)

    logger.info(
        "用户退出全部设备 | user_id=%d | 撤销 %d 个 Token",
        current_user.id,
        count,
    )
    return MessageResponse(
        success=True,
        message=f"已退出所有设备（撤销 {count} 个 Refresh Token）",
    )


@router.get("/auth/me", response_model=dict)
async def get_me(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """获取当前用户信息 — 不返回 password_hash。"""
    auth_service = AuthService(db)
    return auth_service.get_current_user_info(current_user.id)


@router.post("/auth/change-password", response_model=MessageResponse)
async def change_password(
    body: ChangePasswordRequest,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """修改密码。

    修改成功后:
    - 撤销该用户所有 Refresh Token（强制重新登录）
    - 不在响应中返回密码信息
    """
    auth_service = AuthService(db)

    try:
        auth_service.change_password(current_user, body.old_password, body.new_password)
    except AuthenticationError as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)

    logger.info("密码修改成功 | user_id=%d", current_user.id)
    return MessageResponse(
        success=True,
        message="密码修改成功，所有设备已退出，请重新登录",
    )
