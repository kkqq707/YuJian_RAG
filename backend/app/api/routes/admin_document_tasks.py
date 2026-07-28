"""文档后台任务管理路由 (Phase 8)

全部端点需要管理员权限。

端点:
- GET    /api/v1/admin/document-tasks                    — 任务列表
- GET    /api/v1/admin/document-tasks/{task_id}           — 任务详情
- POST   /api/v1/admin/document-tasks/{task_id}/cancel    — 取消任务
- POST   /api/v1/admin/document-tasks/{task_id}/retry     — 重试任务
- GET    /api/v1/admin/document-tasks/metrics             — 任务指标
"""

from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.orm import Session

from backend.app.database import get_db
from backend.app.models.user import User
from backend.app.schemas.document_task import (
    DocumentTaskDetailResponse,
    DocumentTaskItem,
    DocumentTaskListResponse,
    DocumentTaskMetrics,
    TaskActionResponse,
)
from backend.app.security.dependencies import require_admin
from backend.app.services.document_task_service import DocumentTaskService
from backend.app.services.audit_service import AuditService

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/admin/document-tasks",
    tags=["管理员 - 文档任务管理"],
    dependencies=[Depends(require_admin)],
)


def _get_client_info(request: Request) -> tuple:
    ip = request.client.host if request.client else None
    ua = request.headers.get("User-Agent")
    return ip, ua


# ---------------------------------------------------------------------------
# 任务列表
# ---------------------------------------------------------------------------


@router.get("", response_model=DocumentTaskListResponse, summary="获取文档任务列表")
async def list_tasks(
    request: Request,
    status: Optional[str] = Query(None, description="过滤状态: pending | running | completed | failed | cancelled"),
    task_type: Optional[str] = Query(None, description="过滤类型: index_document | rebuild_knowledge_base"),
    document_id: Optional[str] = Query(None, description="过滤文档 ID"),
    offset: int = Query(0, ge=0, description="分页偏移"),
    limit: int = Query(50, ge=1, le=200, description="每页数量"),
    current_user: User = Depends(require_admin),
):
    """获取文档后台任务列表，支持按状态、类型、文档筛选。"""
    service = DocumentTaskService()
    try:
        tasks, total = service.list_tasks(
            status=status,
            task_type=task_type,
            document_id=document_id,
            offset=offset,
            limit=limit,
        )
        return DocumentTaskListResponse(
            success=True,
            total=total,
            tasks=[DocumentTaskItem(**t) for t in tasks],
        )
    except Exception as e:
        logger.error("获取任务列表失败: %s", str(e)[:300])
        return DocumentTaskListResponse(success=True, total=0, tasks=[])


# ---------------------------------------------------------------------------
# 任务详情
# ---------------------------------------------------------------------------


@router.get("/{task_id}", response_model=DocumentTaskDetailResponse, summary="获取任务详情")
async def get_task_detail(
    task_id: int,
    request: Request,
    current_user: User = Depends(require_admin),
):
    """获取单个任务详情。"""
    service = DocumentTaskService()
    detail = service.get_task_detail(task_id)

    if detail is None:
        raise HTTPException(status_code=404, detail="任务不存在")

    return DocumentTaskDetailResponse(
        success=True,
        task=DocumentTaskItem(**detail),
    )


# ---------------------------------------------------------------------------
# 取消任务
# ---------------------------------------------------------------------------


@router.post("/{task_id}/cancel", response_model=TaskActionResponse, summary="取消任务")
async def cancel_task(
    task_id: int,
    request: Request,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """取消文档任务。

    仅允许取消 pending 或 running 状态的任务。
    pending → 直接 cancelled
    running → 先 cancel_requested，worker 在检查点处理

    需要管理员权限。
    """
    service = DocumentTaskService()
    result = service.cancel_task(task_id)

    if not result["success"]:
        status_code = 404 if "不存在" in result.get("message", "") else 409
        raise HTTPException(
            status_code=status_code,
            detail=result.get("message", "取消失败"),
        )

    # 审计日志
    ip, ua = _get_client_info(request)
    audit = AuditService(db)
    audit.log(
        admin_user=current_user,
        action="task_cancel",
        target_type="document_task",
        target_id=str(task_id),
        detail=f"取消任务: {result.get('message', '')}",
        ip_address=ip,
        user_agent=ua,
    )

    return TaskActionResponse(**result)


# ---------------------------------------------------------------------------
# 重试任务
# ---------------------------------------------------------------------------


@router.post("/{task_id}/retry", response_model=TaskActionResponse, summary="重试任务")
async def retry_task(
    task_id: int,
    request: Request,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """重试失败或已取消的任务。

    仅允许重试 failed 或 cancelled 状态的任务。
    创建新任务记录，关联原任务。

    需要管理员权限。
    """
    service = DocumentTaskService()
    try:
        new_task = service.retry_task(task_id)
    except ValueError as e:
        error_msg = str(e)
        status_code = 404 if "不存在" in error_msg else 409
        raise HTTPException(status_code=status_code, detail=error_msg)

    # 审计日志
    ip, ua = _get_client_info(request)
    audit = AuditService(db)
    audit.log(
        admin_user=current_user,
        action="task_retry",
        target_type="document_task",
        target_id=str(task_id),
        detail=f"重试任务: old={task_id} → new={new_task.id}",
        ip_address=ip,
        user_agent=ua,
    )

    return TaskActionResponse(
        success=True,
        message=f"已创建重试任务 (id={new_task.id})",
        task_id=new_task.id,
        new_status="pending",
    )


# ---------------------------------------------------------------------------
# 任务指标
# ---------------------------------------------------------------------------


@router.get(
    "/metrics/summary",
    response_model=DocumentTaskMetrics,
    summary="获取任务运行指标",
)
async def get_task_metrics(
    request: Request,
    current_user: User = Depends(require_admin),
):
    """获取文档任务运行指标（进程内，重启归零）。

    需要管理员权限。
    """
    service = DocumentTaskService()
    return DocumentTaskMetrics(**service.get_metrics())
