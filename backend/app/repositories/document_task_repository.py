"""文档任务仓库 (Phase 8)

提供 DocumentTask 的数据库 CRUD 操作。
使用 SQLAlchemy Session，每次操作独立短事务。
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from backend.app.models.document_task import DocumentTask

logger = logging.getLogger(__name__)

# 任务状态常量
TASK_STATUS_PENDING = "pending"
TASK_STATUS_RUNNING = "running"
TASK_STATUS_COMPLETED = "completed"
TASK_STATUS_FAILED = "failed"
TASK_STATUS_CANCEL_REQUESTED = "cancel_requested"
TASK_STATUS_CANCELLED = "cancelled"

# 终态
TASK_TERMINAL_STATES = {TASK_STATUS_COMPLETED, TASK_STATUS_FAILED, TASK_STATUS_CANCELLED}

# 活跃状态（非终态）
TASK_ACTIVE_STATES = {TASK_STATUS_PENDING, TASK_STATUS_RUNNING, TASK_STATUS_CANCEL_REQUESTED}

# 任务类型
TASK_TYPE_INDEX_DOCUMENT = "index_document"
TASK_TYPE_REBUILD_DOCUMENT = "rebuild_document"
TASK_TYPE_DELETE_DOCUMENT_VECTORS = "delete_document_vectors"
TASK_TYPE_REBUILD_KNOWLEDGE_BASE = "rebuild_knowledge_base"

# 错误代码
ERR_TASK_INTERRUPTED = "TASK_INTERRUPTED"
ERR_DOCUMENT_PARSE_TIMEOUT = "DOCUMENT_PARSE_TIMEOUT"
ERR_DOCUMENT_INDEX_TIMEOUT = "DOCUMENT_INDEX_TIMEOUT"
ERR_DUPLICATE_TASK = "DUPLICATE_TASK"
ERR_TASK_NOT_FOUND = "TASK_NOT_FOUND"
ERR_TASK_CANNOT_CANCEL = "TASK_CANNOT_CANCEL"
ERR_TASK_CANNOT_RETRY = "TASK_CANNOT_RETRY"
ERR_ACTIVE_TASK_EXISTS = "ACTIVE_TASK_EXISTS"
ERR_FILE_NOT_FOUND = "FILE_NOT_FOUND"


class DocumentTaskRepository:
    """DocumentTask 数据库操作仓库。"""

    def __init__(self, db: Session):
        self.db = db

    # ------------------------------------------------------------------
    # 创建
    # ------------------------------------------------------------------

    def create_task(
        self,
        document_id: str,
        task_type: str = TASK_TYPE_INDEX_DOCUMENT,
        created_by: str = "admin",
        original_task_id: Optional[int] = None,
        retry_count: int = 0,
    ) -> DocumentTask:
        """创建新的文档任务记录。

        Raises ValueError 如果同一文档已有冲突的活跃任务。
        """
        # 检查冲突
        existing = self._find_conflicting_task(document_id, task_type)
        if existing:
            raise ValueError(
                f"{ERR_DUPLICATE_TASK}: 文档 {document_id} 已有活跃的 {task_type} 任务 (task_id={existing.id})"
            )

        task = DocumentTask(
            document_id=document_id,
            task_type=task_type,
            status=TASK_STATUS_PENDING,
            progress=0,
            created_by=created_by,
            created_at=datetime.now(timezone.utc),
            retry_count=retry_count,
            original_task_id=original_task_id,
        )
        self.db.add(task)
        self.db.flush()
        logger.info(
            "任务已创建: id=%d, doc=%s, type=%s", task.id, document_id, task_type
        )
        return task

    def _find_conflicting_task(
        self, document_id: str, task_type: str
    ) -> Optional[DocumentTask]:
        """查找同一文档的冲突活跃任务。"""
        stmt = select(DocumentTask).where(
            DocumentTask.document_id == document_id,
            DocumentTask.task_type == task_type,
            DocumentTask.status.in_(TASK_ACTIVE_STATES),
        )
        return self.db.execute(stmt).scalar_one_or_none()

    # ------------------------------------------------------------------
    # 查询
    # ------------------------------------------------------------------

    def get_task(self, task_id: int) -> Optional[DocumentTask]:
        """获取任务详情。"""
        return self.db.get(DocumentTask, task_id)

    def list_tasks(
        self,
        status: Optional[str] = None,
        task_type: Optional[str] = None,
        document_id: Optional[str] = None,
        offset: int = 0,
        limit: int = 50,
    ) -> tuple[list[DocumentTask], int]:
        """分页查询任务列表，支持筛选。"""
        stmt = select(DocumentTask)

        if status:
            stmt = stmt.where(DocumentTask.status == status)
        if task_type:
            stmt = stmt.where(DocumentTask.task_type == task_type)
        if document_id:
            stmt = stmt.where(DocumentTask.document_id == document_id)

        # 计数
        count_stmt = select(func.count()).select_from(stmt.subquery())
        total = self.db.execute(count_stmt).scalar() or 0

        # 分页
        stmt = stmt.order_by(DocumentTask.created_at.desc()).offset(offset).limit(limit)
        tasks = list(self.db.execute(stmt).scalars().all())

        return tasks, total

    def get_tasks_by_document_id(
        self, document_id: str, include_terminal: bool = False
    ) -> list[DocumentTask]:
        """获取文档的所有任务。"""
        stmt = select(DocumentTask).where(
            DocumentTask.document_id == document_id
        )
        if not include_terminal:
            stmt = stmt.where(DocumentTask.status.in_(TASK_ACTIVE_STATES))
        return list(self.db.execute(stmt).scalars().all())

    def get_running_tasks(self) -> list[DocumentTask]:
        """获取所有 running 状态的任务（启动恢复用）。"""
        stmt = select(DocumentTask).where(
            DocumentTask.status == TASK_STATUS_RUNNING
        )
        return list(self.db.execute(stmt).scalars().all())

    def get_pending_tasks(self, limit: int = 20) -> list[DocumentTask]:
        """获取待处理的任务（按创建时间排序）。"""
        stmt = (
            select(DocumentTask)
            .where(DocumentTask.status == TASK_STATUS_PENDING)
            .order_by(DocumentTask.created_at.asc())
            .limit(limit)
        )
        return list(self.db.execute(stmt).scalars().all())

    def count_by_status(self, status: str) -> int:
        """统计指定状态的任务数。"""
        stmt = select(func.count()).where(DocumentTask.status == status)
        return self.db.execute(stmt).scalar() or 0

    def has_active_task_for_document(self, document_id: str) -> bool:
        """检查文档是否有活跃任务。"""
        stmt = select(func.count()).where(
            DocumentTask.document_id == document_id,
            DocumentTask.status.in_(TASK_ACTIVE_STATES),
        )
        count = self.db.execute(stmt).scalar() or 0
        return count > 0

    # ------------------------------------------------------------------
    # 更新
    # ------------------------------------------------------------------

    def update_task_status(
        self,
        task: DocumentTask,
        status: str,
        **kwargs,
    ) -> None:
        """更新任务状态和相关字段。"""
        task.status = status

        now = datetime.now(timezone.utc)
        if status == TASK_STATUS_RUNNING and not task.started_at:
            task.started_at = now
        elif status == TASK_STATUS_COMPLETED:
            task.completed_at = now
            task.progress = 100
        elif status == TASK_STATUS_FAILED:
            task.completed_at = now
        elif status == TASK_STATUS_CANCELLED:
            task.cancelled_at = now

        for key, value in kwargs.items():
            if hasattr(task, key):
                setattr(task, key, value)

        self.db.flush()

    def update_task_progress(
        self,
        task: DocumentTask,
        progress: int,
        current_step: Optional[str] = None,
    ) -> None:
        """更新任务进度。"""
        task.progress = max(0, min(100, progress))
        if current_step:
            task.current_step = current_step[:128]
        task.heartbeat_at = datetime.now(timezone.utc)
        self.db.flush()

    def mark_interrupted_tasks(self) -> int:
        """将 running 状态的任务标记为 interrupted（启动恢复）。

        Returns 更新的任务数。
        """
        tasks = self.get_running_tasks()
        count = 0
        for task in tasks:
            task.status = TASK_STATUS_FAILED
            task.error_code = ERR_TASK_INTERRUPTED
            task.error_message = "应用异常重启，任务中断"
            task.completed_at = datetime.now(timezone.utc)
            count += 1
            logger.warning(
                "任务中断: id=%d, doc=%s, type=%s (应用重启)",
                task.id, task.document_id, task.task_type,
            )
        if count:
            self.db.flush()
        return count

    def get_stats(self) -> dict:
        """获取任务统计信息。"""
        stats = {}
        for status_name in [
            TASK_STATUS_PENDING, TASK_STATUS_RUNNING,
            TASK_STATUS_COMPLETED, TASK_STATUS_FAILED,
            TASK_STATUS_CANCELLED, TASK_STATUS_CANCEL_REQUESTED,
        ]:
            stats[status_name] = self.count_by_status(status_name)
        return stats
