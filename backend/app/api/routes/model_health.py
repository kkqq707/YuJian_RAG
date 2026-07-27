"""模型健康检查路由 — GET /api/system/model-health

独立路由，直接注册到 FastAPI app，不经过 /api/v1 前缀。
用于企业离线部署时检查 Embedding 和 Reranker 模型加载状态。
"""

from __future__ import annotations

from fastapi import APIRouter, Depends

from backend.app.models.user import User
from backend.app.schemas.system import ModelHealthResponse
from backend.app.security.dependencies import get_current_active_user
from backend.app.services.system_service import get_system_service

router = APIRouter(tags=["模型健康检查"])


@router.get("/api/system/model-health", response_model=ModelHealthResponse)
async def model_health(
    current_user: User = Depends(get_current_active_user),
):
    """获取 Embedding 和 Reranker 模型健康状态。

    返回每个模型的名称、加载状态、本地路径和加载模式。
    用于企业离线部署诊断。

    需要登录。
    """
    service = get_system_service()
    health = service.get_model_health()
    return ModelHealthResponse(**health)
