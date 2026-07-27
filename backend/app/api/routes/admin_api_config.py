"""管理员 API 配置路由

全部端点需要管理员权限 (require_admin)。

端点:
- GET  /api/v1/admin/api-config        — 获取当前 LLM 配置
- POST /api/v1/admin/api-config        — 保存 LLM 配置
- POST /api/v1/admin/api-config/test   — 测试 LLM 连接
- GET  /api/v1/admin/models            — 获取可用模型列表
- GET  /api/v1/admin/security/status   — 获取安全状态

安全:
- 不返回 API Key 明文
- 不返回 JWT Secret
- 测试连接不返回完整异常堆栈
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from backend.app.database import get_db
from backend.app.models.user import User
from backend.app.schemas.admin_api_config import (
    LLMConfigRequest,
    LLMConfigResponse,
    ModelItem,
    ModelListResponse,
    SecurityStatusResponse,
    TestConnectionRequest,
    TestConnectionResponse,
)
from backend.app.security.dependencies import require_admin
from backend.app.services.audit_service import AuditService
from backend.app.services.llm_config_service import (
    LLMConfigData,
    get_active_llm_config,
    get_available_models,
    get_llm_config_for_display,
    refresh_cache,
    save_llm_config,
    test_llm_connection_with_config,
)
from backend.app.services.encryption_service import get_encryption_key

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/admin",
    tags=["管理员 - API 配置"],
    dependencies=[Depends(require_admin)],
)


def _get_client_info(request: Request) -> tuple:
    """提取客户端信息用于审计日志。"""
    ip = request.client.host if request.client else None
    ua = request.headers.get("User-Agent")
    return ip, ua


# ---------------------------------------------------------------------------
# LLM 配置 CRUD
# ---------------------------------------------------------------------------


@router.get(
    "/api-config",
    response_model=LLMConfigResponse,
    summary="获取当前 LLM 配置",
)
async def get_api_config(
    request: Request,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """获取当前启用的 LLM 配置。

    API Key 返回脱敏后的掩码（如 sk-****...****xxxx）。
    不返回明文 API Key。

    需要管理员权限。
    """
    config = get_llm_config_for_display(db)
    return LLMConfigResponse(**config)


@router.post(
    "/api-config",
    response_model=LLMConfigResponse,
    summary="保存 LLM 配置",
)
async def save_api_config(
    body: LLMConfigRequest,
    request: Request,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """保存或更新 LLM 配置。

    - API Key 在服务端使用 AES 加密后存储
    - 启用新配置时自动禁用其他配置
    - 保存后自动刷新缓存

    需要管理员权限。
    """
    # 获取现有配置 ID（如果有）
    existing = get_active_llm_config()
    config_id = existing.id if existing else None

    data = LLMConfigData(
        id=config_id,
        provider=body.provider,
        base_url=body.base_url,
        api_key=body.api_key,
        model=body.model,
        enabled=body.enabled,
    )

    saved = save_llm_config(data)

    # 审计日志（不记录 API Key 内容）
    ip, ua = _get_client_info(request)
    audit = AuditService(db)
    audit.log(
        admin_user=current_user,
        action="llm_config_update",
        target_type="system",
        detail=f"修改AI配置: provider={body.provider}, model={body.model}",
        ip_address=ip,
        user_agent=ua,
    )

    # 返回脱敏后的配置
    result = get_llm_config_for_display(db)
    return LLMConfigResponse(**result)


# ---------------------------------------------------------------------------
# 测试连接
# ---------------------------------------------------------------------------


@router.post(
    "/api-config/test",
    response_model=TestConnectionResponse,
    summary="测试 LLM 连接",
)
async def test_connection(
    body: TestConnectionRequest,
    request: Request,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """使用给定配置测试 LLM 连接。

    发送最小测试消息 "hello"，验证连接可用性。
    返回成功/失败、模型名称、响应延迟。

    安全:
    - 不返回 API Key
    - 不返回 Token
    - 不返回完整异常堆栈

    需要管理员权限。
    """
    result = test_llm_connection_with_config(
        base_url=body.base_url,
        api_key=body.api_key,
        model=body.model,
    )

    # 审计日志（不记录 API Key）
    ip, ua = _get_client_info(request)
    audit = AuditService(db)
    audit.log(
        admin_user=current_user,
        action="llm_connection_test",
        target_type="system",
        detail=f"测试API连接: model={body.model}, result={'success' if result['success'] else 'failed'}",
        ip_address=ip,
        user_agent=ua,
        status="success" if result["success"] else "failed",
    )

    return TestConnectionResponse(
        success=result["success"],
        model=result["model"],
        latency_ms=result.get("latency_ms", 0),
        response_preview=result.get("response_preview", ""),
        error=result.get("error"),
    )


@router.post(
    "/api-config/test-saved",
    response_model=TestConnectionResponse,
    summary="测试已保存的 LLM 配置连接",
)
async def test_saved_connection(
    request: Request,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """使用当前数据库中已保存的 LLM 配置测试连接。

    无需传入 API Key（从数据库解密读取），更安全。

    - 成功: 返回模型可用、响应延迟
    - 失败: 返回真实原因（不泄露 API Key）

    需要管理员权限。
    """
    # 从数据库获取已保存的配置
    existing = get_active_llm_config()
    if not existing or not existing.api_key:
        raise HTTPException(
            status_code=400,
            detail="尚未配置 LLM 服务，请先保存 AI 服务配置后再测试连接",
        )

    result = test_llm_connection_with_config(
        base_url=existing.base_url,
        api_key=existing.api_key,
        model=existing.model,
    )

    # 审计日志（不记录 API Key）
    ip, ua = _get_client_info(request)
    audit = AuditService(db)
    audit.log(
        admin_user=current_user,
        action="llm_connection_test_saved",
        target_type="system",
        detail=f"测试已保存API连接: model={existing.model}, result={'success' if result['success'] else 'failed'}",
        ip_address=ip,
        user_agent=ua,
        status="success" if result["success"] else "failed",
    )

    return TestConnectionResponse(
        success=result["success"],
        model=result["model"],
        latency_ms=result.get("latency_ms", 0),
        response_preview=result.get("response_preview", ""),
        error=result.get("error"),
    )


# ---------------------------------------------------------------------------
# 模型列表
# ---------------------------------------------------------------------------


@router.get(
    "/models",
    response_model=ModelListResponse,
    summary="获取可用模型列表",
)
async def list_models(
    request: Request,
    current_user: User = Depends(require_admin),
):
    """获取可用模型列表。

    返回常用 OpenAI-compatible 模型列表，前端动态加载。
    不硬编码模型选项。

    需要管理员权限。
    """
    models = get_available_models()
    return ModelListResponse(
        success=True,
        models=[ModelItem(name=m["name"], provider=m["provider"]) for m in models],
    )


# ---------------------------------------------------------------------------
# 安全状态
# ---------------------------------------------------------------------------


@router.get(
    "/security/status",
    response_model=SecurityStatusResponse,
    summary="获取安全状态",
)
async def security_status(
    request: Request,
    current_user: User = Depends(require_admin),
):
    """获取系统安全状态概览。

    仅返回各个安全组件的初始化状态，不返回任何密钥内容。

    - JWT Secret 是否已初始化
    - 加密主密钥是否已配置
    - LLM 是否已配置

    需要管理员权限。
    """
    import os

    # 检查 JWT
    jwt_initialized = False
    try:
        from backend.app.services.llm_config_service import get_jwt_secret
        secret = get_jwt_secret(db=None)  # type: ignore
        jwt_initialized = bool(secret)
    except Exception:
        # 如果数据库还没初始化，检查环境变量
        jwt_initialized = bool(os.getenv("JWT_SECRET_KEY"))

    # 检查加密密钥
    encryption_configured = False
    try:
        key = get_encryption_key()
        encryption_configured = bool(key)
    except Exception:
        pass

    # 检查 LLM 配置
    llm_configured = False
    try:
        config = get_active_llm_config()
        llm_configured = config is not None and bool(config.api_key)
    except Exception:
        pass

    return SecurityStatusResponse(
        jwt_initialized=jwt_initialized,
        encryption_configured=encryption_configured,
        llm_configured=llm_configured,
    )
