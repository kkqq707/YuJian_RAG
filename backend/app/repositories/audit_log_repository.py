"""管理员审计日志数据仓库"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import desc, func, select
from sqlalchemy.orm import Session

from backend.app.models.admin_audit_log import AdminAuditLog, ACTION_MODULE_MAP


class AuditLogRepository:
    """审计日志数据访问。"""

    def __init__(self, db: Session):
        self.db = db

    def create(
        self,
        admin_id: int,
        admin_username: str,
        action: str,
        module: Optional[str] = None,
        target_type: Optional[str] = None,
        target_id: Optional[str] = None,
        status: str = "success",
        detail: Optional[str] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> AdminAuditLog:
        """创建审计日志记录。

        安全承诺：不记录密码、JWT、API Key、知识库正文。
        """
        # 自动推断模块
        if module is None and action in ACTION_MODULE_MAP:
            module = ACTION_MODULE_MAP[action]

        log_entry = AdminAuditLog(
            admin_id=admin_id,
            admin_username=admin_username,
            action=action,
            module=module,
            target_type=target_type,
            target_id=target_id,
            status=status,
            detail=detail,
            ip_address=ip_address,
            user_agent=user_agent,
        )
        self.db.add(log_entry)
        self.db.flush()
        self.db.refresh(log_entry)
        return log_entry

    def list_logs(
        self,
        skip: int = 0,
        limit: int = 100,
        action: Optional[str] = None,
        admin_id: Optional[int] = None,
        module: Optional[str] = None,
        status: Optional[str] = None,
        username: Optional[str] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
    ) -> list[AdminAuditLog]:
        """查询审计日志列表。"""
        stmt = select(AdminAuditLog).order_by(desc(AdminAuditLog.created_at))

        if action:
            stmt = stmt.where(AdminAuditLog.action == action)
        if admin_id is not None:
            stmt = stmt.where(AdminAuditLog.admin_id == admin_id)
        if module:
            stmt = stmt.where(AdminAuditLog.module == module)
        if status:
            stmt = stmt.where(AdminAuditLog.status == status)
        if username:
            stmt = stmt.where(AdminAuditLog.admin_username.contains(username))
        if start_time:
            stmt = stmt.where(AdminAuditLog.created_at >= start_time)
        if end_time:
            stmt = stmt.where(AdminAuditLog.created_at <= end_time)

        stmt = stmt.offset(skip).limit(limit)
        return list(self.db.execute(stmt).scalars().all())

    def count_logs(
        self,
        action: Optional[str] = None,
        admin_id: Optional[int] = None,
        module: Optional[str] = None,
        status: Optional[str] = None,
        username: Optional[str] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
    ) -> int:
        """统计日志记录数。"""
        stmt = select(func.count()).select_from(AdminAuditLog)
        if action:
            stmt = stmt.where(AdminAuditLog.action == action)
        if admin_id is not None:
            stmt = stmt.where(AdminAuditLog.admin_id == admin_id)
        if module:
            stmt = stmt.where(AdminAuditLog.module == module)
        if status:
            stmt = stmt.where(AdminAuditLog.status == status)
        if username:
            stmt = stmt.where(AdminAuditLog.admin_username.contains(username))
        if start_time:
            stmt = stmt.where(AdminAuditLog.created_at >= start_time)
        if end_time:
            stmt = stmt.where(AdminAuditLog.created_at <= end_time)
        return self.db.execute(stmt).scalar_one()
