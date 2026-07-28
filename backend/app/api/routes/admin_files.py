"""管理员知识库文件管理路由

全部端点需要管理员权限 (require_admin)。

端点:
- GET    /api/v1/admin/files                    — 知识库文件列表
- POST   /api/v1/admin/files/upload              — 上传知识库文件 (202)
- DELETE /api/v1/admin/files/{file_id}           — 删除知识库文件
- GET    /api/v1/admin/files/{file_id}           — 文件详情（含版本历史）
- GET    /api/v1/admin/files/{file_id}/content   — 文件内容预览（分页）
- POST   /api/v1/admin/files/{file_id}/index    — 单文件索引 (202)
- DELETE /api/v1/admin/files/{file_id}/versions/{version_id} — 删除版本
- POST   /api/v1/admin/files/{file_id}/versions/{version_id}/restore — 恢复版本
- POST   /api/v1/admin/files/rebuild-index       — 重建索引 (202)
- GET    /api/v1/admin/files/index-status        — 索引状态
- GET    /api/v1/admin/files/operation-logs      — 操作日志
"""

from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, Depends, File, HTTPException, Query, Request, UploadFile
from sqlalchemy.orm import Session

from backend.app.config import get_settings
from backend.app.database import get_db
from backend.app.models.user import User
from backend.app.schemas.admin_files import (
    FileContentResponse,
    FileDeleteResponse,
    FileDetailResponse,
    FileListResponse,
    FileUploadResponse,
    IndexStatusResponse,
    OperationLogsResponse,
    RebuildIndexResponse,
    SingleFileIndexResponse,
    VersionActionResponse,
)
from backend.app.schemas.document_task import (
    RebuildAcceptedResponse,
    UploadAcceptedResponse,
)
from backend.app.security.dependencies import require_admin
from backend.app.services.admin_files_service import AdminFilesService
from backend.app.services.audit_service import AuditService
from backend.app.vector_store_runtime import VectorStoreBusyError, DuplicateOperationError

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/admin/files",
    tags=["管理员 - 知识库管理"],
    dependencies=[Depends(require_admin)],
)


def _get_client_info(request: Request) -> tuple:
    """提取客户端信息用于审计日志。"""
    ip = request.client.host if request.client else None
    ua = request.headers.get("User-Agent")
    return ip, ua


# ---------------------------------------------------------------------------
# 文件列表
# ---------------------------------------------------------------------------


@router.get("", response_model=FileListResponse, summary="获取知识库文件列表")
async def list_files(
    request: Request,
    source_type: Optional[str] = Query(None, description="过滤来源类型: builtin | upload"),
    current_user: User = Depends(require_admin),
):
    """获取知识库文件列表，可按来源类型过滤。需要管理员权限。"""
    service = AdminFilesService()
    try:
        result = service.list_files(source_type=source_type)
        return FileListResponse(**result)
    except Exception as e:
        logger.error("获取文件列表失败: %s", str(e)[:300])
        # 即使出错也返回空列表，避免前端显示"服务不可用"
        return FileListResponse(success=True, total=0, files=[])


# ---------------------------------------------------------------------------
# 文件上传（带版本管理）
# ---------------------------------------------------------------------------


@router.post("/upload", summary="上传知识库文件 (Phase 8: 异步处理)")
async def upload_files(
    request: Request,
    files: list[UploadFile] = File(..., description="知识库文件（txt/pdf/docx/md/xlsx，单文件最大 50MB）"),
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """上传知识库文件，文件保存后立即返回 202，索引在后台执行。

    支持格式: txt, pdf, docx, md, xlsx
    单文件最大: 50MB
    一次最多: 5 个文件

    上传成功后返回 task_id 用于追踪处理进度。

    需要管理员权限。
    """
    if not files:
        raise HTTPException(status_code=422, detail="请选择要上传的文件")

    max_files = get_settings().MAX_FILES_PER_UPLOAD_REQUEST
    if len(files) > max_files:
        raise HTTPException(
            status_code=422,
            detail=f"单次最多上传 {max_files} 个文件",
        )

    service = AdminFilesService()
    result = await service.upload_files_async(files, created_by=current_user.username)

    # 审计日志
    ip, ua = _get_client_info(request)
    audit = AuditService(db)
    audit.log(
        admin_user=current_user,
        action="file_upload",
        target_type="knowledge_file",
        detail=f"上传 {result['succeeded']} 个文件, 跳过 {result.get('skipped', 0)} 个, 失败 {result['failed']} 个",
        ip_address=ip,
        user_agent=ua,
    )

    # Phase 8: 返回包含 task 信息的响应
    return result


# ---------------------------------------------------------------------------
# 重建索引
# ---------------------------------------------------------------------------


@router.post("/rebuild-index", summary="重建知识库索引 (Phase 8: 异步处理)")
async def rebuild_index(
    request: Request,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """重建全部上传文件索引（后台异步执行）。

    流程:
    1. 创建重建任务
    2. 入队后台处理
    3. 立即返回 202 + task_id

    可通过 GET /api/v1/admin/document-tasks/{task_id} 追踪进度。

    注意:
    - 仅索引通过上传 API 管理的文件
    - 此操作会清空并重建整个向量库

    需要管理员权限。
    """
    service = AdminFilesService()
    try:
        result = await service.rebuild_index_async(created_by=current_user.username)
    except DuplicateOperationError as e:
        raise HTTPException(status_code=409, detail=e.message)
    except ValueError as e:
        raise HTTPException(status_code=503 if "队列满" in str(e) else 409, detail=str(e))

    # 审计日志
    ip, ua = _get_client_info(request)
    audit = AuditService(db)
    audit.log(
        admin_user=current_user,
        action="index_rebuild",
        target_type="system",
        detail=f"创建重建任务: task_id={result.get('task_id')}",
        ip_address=ip,
        user_agent=ua,
    )

    return result


# ---------------------------------------------------------------------------
# 索引状态
# ---------------------------------------------------------------------------


@router.get("/index-status", response_model=IndexStatusResponse, summary="查看索引状态")
async def index_status(
    request: Request,
    current_user: User = Depends(require_admin),
):
    """查看知识库索引状态和统计信息。

    返回 Chroma 向量数、已索引文件数、待索引文件数、总片段数等。

    需要管理员权限。
    """
    service = AdminFilesService()
    try:
        result = service.get_index_status()
        return IndexStatusResponse(**result)
    except Exception as e:
        logger.error("获取索引状态失败: %s", str(e)[:300])
        return IndexStatusResponse(
            success=True,
            chroma_status="error",
            total_vectors=0,
            indexed_files=0,
            pending_files=0,
            total_chunks=0,
            consistency_note=f"获取状态时出错: {str(e)[:100]}",
        )


# ---------------------------------------------------------------------------
# 操作日志
# ---------------------------------------------------------------------------


@router.get("/operation-logs", response_model=OperationLogsResponse, summary="查看操作日志")
async def operation_logs(
    request: Request,
    limit: int = Query(50, ge=1, le=200, description="返回条数"),
    current_user: User = Depends(require_admin),
):
    """获取知识库操作日志（上传、更新版本、删除、重新索引等）。

    需要管理员权限。
    """
    service = AdminFilesService()
    try:
        result = service.get_operation_logs(limit=limit)
        return OperationLogsResponse(**result)
    except Exception as e:
        logger.error("获取操作日志失败: %s", str(e)[:300])
        return OperationLogsResponse(success=True, total=0, logs=[])


# ---------------------------------------------------------------------------
# 文件详情（含版本历史）
# ---------------------------------------------------------------------------


@router.get("/{file_id}", response_model=FileDetailResponse, summary="获取文件详情")
async def get_file_detail(
    request: Request,
    file_id: str,
    current_user: User = Depends(require_admin),
):
    """获取文件详情，包含版本历史、索引信息、向量数量。需要管理员权限。"""
    service = AdminFilesService()
    result = service.get_file_detail(file_id)
    return FileDetailResponse(**result)


# ---------------------------------------------------------------------------
# 文件内容预览（分页）
# ---------------------------------------------------------------------------


@router.get("/{file_id}/content", response_model=FileContentResponse, summary="预览文件内容")
async def get_file_content(
    request: Request,
    file_id: str,
    page: int = Query(1, ge=1, description="页码，从 1 开始"),
    page_size: int = Query(10000, ge=1000, le=50000, description="每页字符数"),
    current_user: User = Depends(require_admin),
):
    """获取文件文本内容（分页加载）。

    支持格式: TXT, MD, PDF, DOCX

    超过 page_size 字符自动分页，避免一次性加载大文件。
    返回前5个chunk预览供参考。

    需要管理员权限。
    """
    service = AdminFilesService()
    result = service.get_file_content(file_id, page=page, page_size=page_size)
    return FileContentResponse(**result)


# ---------------------------------------------------------------------------
# 文件删除
# ---------------------------------------------------------------------------


@router.delete("/{file_id}", response_model=FileDeleteResponse, summary="删除知识库文件")
async def delete_file(
    request: Request,
    file_id: str,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """删除知识库文件。

    删除流程:
    1. 从 SQLite 标记删除
    2. 从 Chroma 删除对应 chunks
    3. 删除磁盘文件
    4. 刷新索引统计

    需要管理员权限。
    """
    service = AdminFilesService()
    try:
        result = await service.delete_file(file_id)
    except VectorStoreBusyError as e:
        raise HTTPException(status_code=503, detail=e.message)

    # 审计日志
    ip, ua = _get_client_info(request)
    audit = AuditService(db)
    audit.log(
        admin_user=current_user,
        action="file_delete",
        target_type="knowledge_file",
        target_id=file_id,
        detail=f"删除文件, 移除 {result['deleted_chunks']} 个 chunks",
        ip_address=ip,
        user_agent=ua,
    )

    if not result["success"]:
        raise HTTPException(status_code=400, detail=result["message"])

    return FileDeleteResponse(**result)


# ---------------------------------------------------------------------------
# 删除版本
# ---------------------------------------------------------------------------


@router.delete("/{file_id}/versions/{version_id}", response_model=VersionActionResponse, summary="删除文件版本")
async def delete_version(
    request: Request,
    file_id: str,
    version_id: str,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """删除文件的某个版本记录。

    如果删除的是当前版本，自动回退到上一个可用版本。
    至少保留一个版本，无法删除最后一个版本。

    需要管理员权限。
    """
    service = AdminFilesService()
    result = service.delete_version(file_id, version_id)

    # 审计日志
    ip, ua = _get_client_info(request)
    audit = AuditService(db)
    audit.log(
        admin_user=current_user,
        action="file_delete",
        target_type="knowledge_file_version",
        target_id=version_id,
        detail=f"删除版本: {result.get('message', '')}",
        ip_address=ip,
        user_agent=ua,
    )

    if not result["success"]:
        raise HTTPException(status_code=400, detail=result["message"])

    return VersionActionResponse(**result)


# ---------------------------------------------------------------------------
# 恢复版本
# ---------------------------------------------------------------------------


@router.post("/{file_id}/versions/{version_id}/restore", response_model=VersionActionResponse, summary="恢复文件版本")
async def restore_version(
    request: Request,
    file_id: str,
    version_id: str,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """恢复到文件的某个历史版本。

    恢复操作会更新文件的 current_version、file_hash、file_size。

    需要管理员权限。
    """
    service = AdminFilesService()
    result = service.restore_version(file_id, version_id)

    # 审计日志
    ip, ua = _get_client_info(request)
    audit = AuditService(db)
    audit.log(
        admin_user=current_user,
        action="file_index",
        target_type="knowledge_file_version",
        target_id=version_id,
        detail=f"恢复版本: {result.get('message', '')}",
        ip_address=ip,
        user_agent=ua,
    )

    if not result["success"]:
        raise HTTPException(status_code=400, detail=result["message"])

    return VersionActionResponse(**result)


# ---------------------------------------------------------------------------
# 单文件索引
# ---------------------------------------------------------------------------


@router.post("/{file_id}/index", summary="为单个文件建立索引 (Phase 8: 异步处理)")
async def index_single_file(
    request: Request,
    file_id: str,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """为指定文件创建后台索引任务。

    创建任务后立即返回 202，索引在后台执行。
    可通过 GET /api/v1/admin/document-tasks?document_id={file_id} 追踪进度。

    需要管理员权限。
    """
    service = AdminFilesService()
    try:
        result = await service.index_single_file_async(file_id, created_by=current_user.username)
    except ValueError as e:
        error_str = str(e)
        if "队列满" in error_str:
            raise HTTPException(status_code=503, detail=error_str)
        if "已有活跃" in error_str or "冲突" in error_str:
            raise HTTPException(status_code=409, detail=error_str)
        raise HTTPException(status_code=400, detail=error_str)

    # 审计日志
    ip, ua = _get_client_info(request)
    audit = AuditService(db)
    audit.log(
        admin_user=current_user,
        action="file_index",
        target_type="knowledge_file",
        target_id=file_id,
        detail=f"创建索引任务: task_id={result.get('task_id')}",
        ip_address=ip,
        user_agent=ua,
    )

    return result
