"""管理员系统管理路由

全部端点需要管理员权限 (require_admin)。

端点:
- GET  /api/v1/admin/system              — 完整系统状态
- GET  /api/v1/admin/system/logs         — 审计日志
- GET  /api/v1/admin/system/health       — 健康检查
- GET  /api/v1/admin/system/info         — 系统信息
- GET  /api/v1/admin/system/modules      — 模块列表
- GET  /api/v1/admin/system/settings     — 系统设置
- PUT  /api/v1/admin/system/settings     — 保存系统设置
- POST /api/v1/admin/system/jwt/regenerate — 重新生成 JWT
- GET  /api/v1/admin/system/security     — 安全设置
- GET  /api/v1/admin/logs                — 系统日志（增强版）
- GET  /api/v1/admin/logs/{id}           — 日志详情
"""

from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.database import get_db
from backend.app.models.user import User
from backend.app.schemas.admin_system import (
    AdminSystemStatusResponse,
    AuditLogResponse,
    BackupResponse,
    BackupListResponse,
    RestoreRequest,
    RestoreResponse,
)
from backend.app.schemas.admin_logs import (
    HealthCheckResponse,
    JWTRegenResponse,
    SaveSettingsBulkRequest,
    SecuritySettingsResponse,
    SystemInfoResponse,
    SystemLogDetail,
    SystemLogListResponse,
    SystemSettingsResponse,
)
from backend.app.security.dependencies import require_admin
from backend.app.services.admin_system_service import AdminSystemService
from backend.app.services.system_settings_service import SystemSettingsService
from backend.app.services.audit_service import AuditService

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/admin/system",
    tags=["管理员 - 系统管理"],
    dependencies=[Depends(require_admin)],
)


def _get_client_info(request: Request) -> tuple:
    """提取客户端信息用于审计日志。"""
    ip = request.client.host if request.client else None
    ua = request.headers.get("User-Agent")
    return ip, ua


# ---------------------------------------------------------------------------
# 系统状态
# ---------------------------------------------------------------------------


@router.get("", response_model=AdminSystemStatusResponse, summary="获取完整系统状态")
async def system_status(
    request: Request,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """获取完整系统诊断信息。

    包含:
    - 各组件状态: Embedding / DeepSeek / Chroma / SQLite
    - 统计信息: 文件数、用户数、Chunk 数、向量数等
    - API 版本

    不返回 API Key、绝对路径、环境变量。

    需要管理员权限。
    """
    service = AdminSystemService(db)
    result = service.get_full_status()
    return AdminSystemStatusResponse(**result)


# ---------------------------------------------------------------------------
# 审计日志
# ---------------------------------------------------------------------------


@router.get("/logs", response_model=AuditLogResponse, summary="查看审计日志")
async def audit_logs(
    request: Request,
    skip: int = Query(0, ge=0, description="分页偏移"),
    limit: int = Query(100, ge=1, le=500, description="每页数量"),
    action: Optional[str] = Query(None, description="操作类型过滤"),
    admin_id: Optional[int] = Query(None, description="管理员 ID 过滤"),
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """查看管理员操作审计日志。

    支持按操作类型和管理员 ID 过滤。
    日志不包含密码、JWT、API Key、知识库正文。

    需要管理员权限。
    """
    service = AdminSystemService(db)
    result = service.get_audit_logs(
        skip=skip,
        limit=limit,
        action=action,
        admin_id=admin_id,
    )
    return AuditLogResponse(**result)


# ---------------------------------------------------------------------------
# 健康检查
# ---------------------------------------------------------------------------


@router.get("/health", response_model=HealthCheckResponse, summary="系统健康检查")
async def health_check(
    request: Request,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """系统健康检查。

    检查 Backend API、Database、Chroma、LLM、Embedding 状态。

    禁止暴露异常堆栈和 API Key。

    需要管理员权限。
    """
    service = AdminSystemService(db)
    result = service.get_health_check()
    return HealthCheckResponse(**result)


# ---------------------------------------------------------------------------
# 系统信息
# ---------------------------------------------------------------------------


@router.get("/info", response_model=SystemInfoResponse, summary="获取系统信息")
async def system_info(
    request: Request,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """获取系统基本信息（名称、版本、部署模式等）。

    需要管理员权限。
    """
    service = AdminSystemService(db)
    result = service.get_system_info()
    return SystemInfoResponse(**result)


# ---------------------------------------------------------------------------
# 模块列表
# ---------------------------------------------------------------------------


@router.get("/modules", summary="获取模块列表")
async def module_list(
    request: Request,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """获取系统日志可用的模块过滤列表。

    需要管理员权限。
    """
    service = AdminSystemService(db)
    modules = service.get_module_list()
    return {"success": True, "modules": modules}


# ---------------------------------------------------------------------------
# 安全设置
# ---------------------------------------------------------------------------


@router.get("/security", response_model=SecuritySettingsResponse, summary="获取安全设置")
async def security_settings(
    request: Request,
    current_user: User = Depends(require_admin),
):
    """获取安全设置状态（不返回 Secret 内容）。

    需要管理员权限。
    """
    import os
    from backend.app.config import get_settings
    from backend.app.services.encryption_service import get_encryption_key

    settings = get_settings()

    # JWT 状态
    jwt_initialized = False
    try:
        from backend.app.services.llm_config_service import get_jwt_secret_sync
        secret = get_jwt_secret_sync()
        jwt_initialized = bool(secret)
    except Exception:
        jwt_initialized = bool(os.getenv("JWT_SECRET_KEY"))

    # 加密密钥
    encryption_configured = False
    try:
        key = get_encryption_key()
        encryption_configured = bool(key)
    except Exception:
        pass

    return SecuritySettingsResponse(
        success=True,
        jwt_initialized=jwt_initialized,
        jwt_algorithm=settings.JWT_ALGORITHM,
        access_token_expire_minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES,
        refresh_token_expire_days=settings.REFRESH_TOKEN_EXPIRE_DAYS,
        encryption_configured=encryption_configured,
    )


# ---------------------------------------------------------------------------
# 重新生成 JWT
# ---------------------------------------------------------------------------


@router.post("/jwt/regenerate", response_model=JWTRegenResponse, summary="重新生成 JWT 密钥")
async def regenerate_jwt(
    request: Request,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """重新生成 JWT 签名密钥。

    注意：重新生成后所有用户需要重新登录。

    需要管理员权限。
    """
    import secrets
    from backend.app.services.encryption_service import encrypt
    from backend.app.models.system_config import SystemConfig

    # 生成新密钥
    new_secret = secrets.token_urlsafe(48)

    # 保存到数据库
    stmt = select(SystemConfig).where(SystemConfig.config_key == "jwt_secret_key")
    config = db.execute(stmt).scalar_one_or_none()

    if config:
        config.config_value_encrypted = encrypt(new_secret)
    else:
        config = SystemConfig(
            config_key="jwt_secret_key",
            config_value_encrypted=encrypt(new_secret),
            description="JWT Token 签名密钥（自动生成，禁止修改）",
        )
        db.add(config)

    db.flush()

    # 刷新缓存
    from backend.app.services.llm_config_service import refresh_cache
    refresh_cache()

    # 审计日志
    ip, ua = _get_client_info(request)
    audit = AuditService(db)
    audit.log(
        admin_user=current_user,
        action="jwt_regenerate",
        target_type="system",
        detail="重新生成 JWT 密钥",
        ip_address=ip,
        user_agent=ua,
    )

    logger.warning("JWT 密钥已被管理员 %s 重新生成", current_user.username)

    return JWTRegenResponse(
        success=True,
        message="JWT 密钥已重新生成。所有用户需要重新登录。",
    )


# ---------------------------------------------------------------------------
# 数据备份
# ---------------------------------------------------------------------------


@router.post("/backup", response_model=BackupResponse, summary="创建数据备份")
async def create_backup(
    request: Request,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """创建完整数据备份（SQLite + Chroma + 上传文件）。

    生成 backup_YYYYMMDD_HHMMSS.zip 文件到 storage/backup/ 目录。

    需要管理员权限。
    """
    from backend.app.services.backup_service import BackupService

    service = BackupService()
    result = service.create_backup()

    # 审计日志
    ip, ua = _get_client_info(request)
    audit = AuditService(db)
    audit.log(
        admin_user=current_user,
        action="backup_create",
        target_type="system",
        detail=f"备份数据: {result.file_name} ({result.file_size_bytes} bytes)" if result.success else f"备份失败: {result.error}",
        ip_address=ip,
        user_agent=ua,
    )

    return BackupResponse(
        success=result.success,
        file_name=result.file_name,
        file_size_bytes=result.file_size_bytes,
        file_size_mb=round(result.file_size_bytes / (1024 * 1024), 2) if result.file_size_bytes else None,
        created_at=result.created_at,
        included=result.included,
        error=result.error,
    )


@router.get("/backups", response_model=BackupListResponse, summary="获取备份列表")
async def list_backups(
    request: Request,
    current_user: User = Depends(require_admin),
):
    """获取所有备份文件列表，按时间倒序排列。

    需要管理员权限。
    """
    from backend.app.services.backup_service import BackupService

    service = BackupService()
    backups = service.list_backups()
    return BackupListResponse(success=True, backups=backups)


@router.post("/restore", response_model=RestoreResponse, summary="恢复数据备份")
async def restore_backup(
    body: RestoreRequest,
    request: Request,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """从备份文件恢复数据。

    支持选择性恢复:
    - database: SQLite 数据库
    - chroma: Chroma 向量库
    - uploads: 上传文件

    不指定 targets 时默认恢复全部。

    **注意：恢复会覆盖当前数据，请谨慎操作！**

    需要管理员权限。
    """
    from backend.app.services.backup_service import BackupService

    service = BackupService()

    try:
        result = service.restore_backup(
            file_name=body.file_name,
            targets=body.targets,
            admin_username=current_user.username,
        )
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    # 审计日志
    ip, ua = _get_client_info(request)
    audit = AuditService(db)
    audit.log(
        admin_user=current_user,
        action="backup_restore",
        target_type="system",
        detail=f"恢复备份: {body.file_name}, 目标: {body.targets or ['database', 'chroma', 'uploads']}, 已恢复: {result['restored']}",
        ip_address=ip,
        user_agent=ua,
    )

    return RestoreResponse(
        success=result["success"],
        restored=result["restored"],
        errors=result["errors"],
    )


# ---------------------------------------------------------------------------
# 系统设置
# ---------------------------------------------------------------------------


@router.get("/settings", response_model=SystemSettingsResponse, summary="获取系统设置")
async def get_system_settings(
    request: Request,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """获取所有系统设置（非敏感配置）。

    需要管理员权限。
    """
    service = SystemSettingsService(db)
    service.init_defaults()
    settings = service.get_all_settings()
    return SystemSettingsResponse(success=True, settings=settings)


@router.put("/settings", response_model=SystemSettingsResponse, summary="保存系统设置")
async def save_system_settings(
    request: Request,
    body: SaveSettingsBulkRequest,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """批量保存系统设置。

    保存后即时生效。

    需要管理员权限。
    """
    service = SystemSettingsService(db)
    settings = service.save_settings_bulk(body.settings)

    # 审计日志
    ip, ua = _get_client_info(request)
    audit = AuditService(db)
    audit.log(
        admin_user=current_user,
        action="system_setting_update",
        target_type="system",
        detail=f"更新系统设置: {', '.join(body.settings.keys())}",
        ip_address=ip,
        user_agent=ua,
    )

    return SystemSettingsResponse(success=True, settings=settings)


# ---------------------------------------------------------------------------
# 系统日志路由（/admin/logs 前缀）
# ---------------------------------------------------------------------------

logs_router = APIRouter(
    prefix="/admin/logs",
    tags=["管理员 - 系统日志"],
    dependencies=[Depends(require_admin)],
)


@logs_router.get("", response_model=SystemLogListResponse, summary="获取系统日志")
async def list_system_logs(
    request: Request,
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(50, ge=1, le=200, description="每页数量"),
    module: Optional[str] = Query(None, description="模块过滤"),
    status: Optional[str] = Query(None, description="状态过滤: success | failed | warning"),
    username: Optional[str] = Query(None, description="用户名搜索"),
    start_time: Optional[str] = Query(None, description="开始时间 (ISO 格式)"),
    end_time: Optional[str] = Query(None, description="结束时间 (ISO 格式)"),
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """查看系统运行日志。

    支持按模块、状态、用户名、时间范围过滤。
    默认最近 50 条。
    禁止显示 API Key、密码、JWT、Token、服务器绝对路径。

    需要管理员权限。
    """
    service = AdminSystemService(db)
    result = service.get_system_logs(
        page=page,
        page_size=page_size,
        module=module,
        status=status,
        username=username,
        start_time=start_time,
        end_time=end_time,
    )
    return SystemLogListResponse(**result)


@logs_router.get("/{log_id}", response_model=SystemLogDetail, summary="查看日志详情")
async def get_log_detail(
    log_id: int,
    request: Request,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """查看单条系统日志详情。

    需要管理员权限。
    """
    service = AdminSystemService(db)
    detail = service.get_system_log_detail(log_id)

    if detail is None:
        raise HTTPException(status_code=404, detail="日志记录不存在")

    return SystemLogDetail(**detail)
