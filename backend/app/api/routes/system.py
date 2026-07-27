"""系统状态路由 — 返回安全系统诊断信息

需要登录用户。
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends

from backend.app.models.user import User
from backend.app.schemas.system import SystemStatusResponse, RAGHealthResponse
from backend.app.security.dependencies import get_current_active_user
from backend.app.services.system_service import get_system_service

logger = logging.getLogger(__name__)

router = APIRouter(tags=["系统状态"])


@router.get("/system/status", response_model=SystemStatusResponse)
async def system_status(
    current_user: User = Depends(get_current_active_user),
):
    """获取系统状态 — 不含 API Key / 绝对路径 / 环境变量。

    需要登录。
    """
    service = get_system_service()
    status = service.get_status()
    return SystemStatusResponse(**status)


@router.get("/system/rag-health", response_model=RAGHealthResponse)
async def rag_health(
    current_user: User = Depends(get_current_active_user),
):
    """获取 RAG 系统完整健康检查信息。

    包含:
    - Chroma 向量库状态（集合数、向量数）
    - 文档状态（总数、已索引、失败、待处理）
    - Embedding 模型状态（模型名、加载方式）
    - 最近索引任务信息
    - 最后索引时间

    需要登录。用于管理员首页系统健康面板。
    """
    service = get_system_service()
    health = service.get_rag_health()
    return RAGHealthResponse(**health)
