"""文档后台任务 — 请求与响应模型 (Phase 8)"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


# ---------------------------------------------------------------------------
# 任务条目
# ---------------------------------------------------------------------------


class DocumentTaskItem(BaseModel):
    """文档任务条目（管理员可见）。"""

    id: int = Field(..., description="任务 ID")
    document_id: str = Field(..., description="关联文档 ID")
    task_type: str = Field(..., description="任务类型")
    status: str = Field(..., description="任务状态")
    progress: int = Field(0, description="进度 0-100")
    current_step: Optional[str] = Field(None, description="当前步骤")
    error_code: Optional[str] = Field(None, description="错误代码")
    error_message: Optional[str] = Field(None, description="安全错误摘要")
    created_by: str = Field("admin", description="创建者")
    created_at: Optional[datetime] = Field(None, description="创建时间")
    started_at: Optional[datetime] = Field(None, description="开始时间")
    completed_at: Optional[datetime] = Field(None, description="完成时间")
    cancelled_at: Optional[datetime] = Field(None, description="取消时间")
    retry_count: int = Field(0, description="重试次数")
    original_task_id: Optional[int] = Field(None, description="原任务 ID")
    chunk_count: Optional[int] = Field(None, description="生成 chunk 数")

    model_config = ConfigDict(from_attributes=True)


# ---------------------------------------------------------------------------
# 任务列表
# ---------------------------------------------------------------------------


class DocumentTaskListResponse(BaseModel):
    """任务列表响应。"""

    success: bool = Field(True, description="请求是否成功")
    total: int = Field(0, description="任务总数")
    tasks: list[DocumentTaskItem] = Field(default_factory=list, description="任务列表")


# ---------------------------------------------------------------------------
# 任务详情
# ---------------------------------------------------------------------------


class DocumentTaskDetailResponse(BaseModel):
    """任务详情响应。"""

    success: bool = Field(True, description="请求是否成功")
    task: Optional[DocumentTaskItem] = Field(None, description="任务详情")
    message: Optional[str] = Field(None, description="错误信息")


# ---------------------------------------------------------------------------
# 上传异步响应 (202)
# ---------------------------------------------------------------------------


class UploadAcceptedResponse(BaseModel):
    """文件上传已接受响应（后台处理中）。"""

    success: bool = Field(True)
    message: str = Field("文件已上传，正在等待处理")
    document_id: Optional[str] = Field(None)
    task_id: Optional[int] = Field(None)
    status: str = Field("pending")


class UploadAcceptedResult(BaseModel):
    """单个文件上传结果。"""

    filename: str = Field(...)
    success: bool = Field(False)
    document_id: Optional[str] = Field(None)
    task_id: Optional[int] = Field(None)
    error: Optional[str] = Field(None)
    error_code: Optional[str] = Field(None)
    skipped: bool = Field(False)


# ---------------------------------------------------------------------------
# 取消/重试响应
# ---------------------------------------------------------------------------


class TaskActionResponse(BaseModel):
    """任务操作响应（取消/重试）。"""

    success: bool = Field(True)
    message: str = Field(...)
    task_id: int = Field(...)
    new_status: Optional[str] = Field(None)
    error_code: Optional[str] = Field(None)


# ---------------------------------------------------------------------------
# 重建索引异步响应 (202)
# ---------------------------------------------------------------------------


class RebuildAcceptedResponse(BaseModel):
    """重建索引已接受响应。"""

    success: bool = Field(True)
    message: str = Field("索引重建任务已创建")
    task_id: Optional[int] = Field(None)
    status: str = Field("pending")


# ---------------------------------------------------------------------------
# 任务指标
# ---------------------------------------------------------------------------


class DocumentTaskMetrics(BaseModel):
    """任务运行指标（管理员可见）。"""

    upload_active: int = 0
    upload_waiting: int = 0
    upload_total: int = 0
    upload_rejected_total: int = 0
    document_task_pending: int = 0
    document_task_running: int = 0
    document_task_completed_total: int = 0
    document_task_failed_total: int = 0
    document_task_cancelled_total: int = 0
    document_task_queue_full_total: int = 0
    document_parse_timeout_total: int = 0
    document_index_timeout_total: int = 0
    document_task_average_duration_ms: float = 0.0
