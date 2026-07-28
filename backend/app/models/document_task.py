"""文档后台任务数据模型 (Phase 8)

DocumentTask 记录每个文档后台任务的生命周期:
- 上传后创建 pending 任务
- worker 获取后变为 running
- 完成变为 completed / 失败变为 failed
- 支持取消和重试

所有字段使用安全值，不保存完整 traceback。
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, Integer, String, Text
from sqlalchemy.orm import declarative_base

Base = declarative_base()


class DocumentTask(Base):
    """文档后台任务记录。

    存储在 app.db (SQLAlchemy 管理)，通过 Alembic 迁移。
    """

    __tablename__ = "document_tasks"

    # 主键
    id = Column(Integer, primary_key=True, autoincrement=True)

    # 关联文档 (knowledge_files 表中的 UUID)
    document_id = Column(String(64), nullable=False, index=True)

    # 任务类型
    task_type = Column(
        String(32),
        nullable=False,
        default="index_document",
        comment="index_document | rebuild_document | delete_document_vectors | rebuild_knowledge_base",
    )

    # 任务状态
    status = Column(
        String(20),
        nullable=False,
        default="pending",
        index=True,
        comment="pending | running | completed | failed | cancel_requested | cancelled",
    )

    # 进度 (0-100)
    progress = Column(Integer, nullable=False, default=0)

    # 当前步骤描述 (安全简短)
    current_step = Column(String(128), nullable=True)

    # 错误信息 (限制长度，不保存 traceback)
    error_code = Column(String(64), nullable=True)
    error_message = Column(String(512), nullable=True)

    # 操作者
    created_by = Column(String(64), nullable=False, default="admin")

    # 时间戳
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        index=True,
    )
    started_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    cancelled_at = Column(DateTime(timezone=True), nullable=True)

    # 重试
    retry_count = Column(Integer, nullable=False, default=0)
    original_task_id = Column(Integer, nullable=True)  # 关联原任务

    # worker 标识 (用于启动恢复)
    worker_id = Column(String(64), nullable=True)
    heartbeat_at = Column(DateTime(timezone=True), nullable=True)

    # 结果摘要
    chunk_count = Column(Integer, nullable=True)

    def __repr__(self) -> str:
        return (
            f"DocumentTask(id={self.id}, doc={self.document_id}, "
            f"type={self.task_type}, status={self.status}, progress={self.progress})"
        )
