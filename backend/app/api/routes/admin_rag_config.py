"""管理员 RAG 配置路由 — RAG 3.0 参数管理

权限:
- GET /api/v1/admin/rag-config: 需要管理员权限
- PUT /api/v1/admin/rag-config: 需要管理员权限
- POST /api/v1/admin/rag-config/reset: 需要管理员权限
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from backend.app.database import get_db
from backend.app.models.user import User
from backend.app.schemas.rag_config import (
    RAGConfigResponse,
    RAGConfigSaveResponse,
    RAGConfigUpdateRequest,
)
from backend.app.security.dependencies import require_admin
from backend.app.services import rag_config_service

logger = logging.getLogger(__name__)

router = APIRouter(tags=["RAG配置"])


@router.get("/admin/rag-config", response_model=RAGConfigResponse)
async def get_rag_config(
    request: Request,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """获取当前 RAG 配置。

    需要管理员权限。
    数据库优先，无配置时回退到环境变量/默认值。
    """
    config = rag_config_service.get_rag_config(db)
    return RAGConfigResponse(**config)


@router.put("/admin/rag-config", response_model=RAGConfigSaveResponse)
async def update_rag_config(
    request: Request,
    body: RAGConfigUpdateRequest,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """更新 RAG 配置。

    需要管理员权限。只更新请求中提供的字段（局部更新）。
    修改立即生效，无需重启服务。
    """
    # 只取非 None 字段
    update_data = {k: v for k, v in body.model_dump().items() if v is not None}

    if not update_data:
        config = rag_config_service.get_rag_config(db)
        return RAGConfigSaveResponse(
            success=True,
            message="未提供更新字段，返回当前配置",
            config=RAGConfigResponse(**config),
        )

    # 权重合理性校验
    if "vector_weight" in update_data and "keyword_weight" not in update_data:
        # 自动计算 keyword_weight
        update_data["keyword_weight"] = round(1.0 - update_data["vector_weight"], 2)

    config = rag_config_service.save_rag_config(update_data, db)

    logger.info(
        "RAG 配置已更新 | user=%s | fields=%s",
        current_user.username,
        list(update_data.keys()),
    )

    return RAGConfigSaveResponse(
        success=True,
        message="RAG 配置已更新，新配置立即生效",
        config=RAGConfigResponse(**config),
    )


@router.post("/admin/rag-config/reset", response_model=RAGConfigSaveResponse)
async def reset_rag_config(
    request: Request,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """重置 RAG 配置为默认值。

    需要管理员权限。
    """
    config = rag_config_service.reset_rag_config(db)

    logger.info(
        "RAG 配置已重置为默认值 | user=%s",
        current_user.username,
    )

    return RAGConfigSaveResponse(
        success=True,
        message="RAG 配置已重置为默认值",
        config=RAGConfigResponse(**config),
    )
