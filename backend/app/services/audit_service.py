"""审计日志服务

提供统一的管理员操作审计日志记录。

安全承诺:
- 不记录密码
- 不记录 JWT / API Key
- 不记录知识库正文
"""

from __future__ import annotations

import logging
from typing import Optional

from sqlalchemy.orm import Session

from backend.app.models.user import User
from backend.app.repositories.audit_log_repository import AuditLogRepository

logger = logging.getLogger(__name__)


class AuditService:
    """审计日志服务 — 提供简化的日志记录接口。"""

    def __init__(self, db: Session):
        self.db = db
        self.repo = AuditLogRepository(db)

    def log(
        self,
        admin_user: User,
        action: str,
        target_type: Optional[str] = None,
        target_id: Optional[str] = None,
        detail: Optional[str] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        module: Optional[str] = None,
        status: str = "success",
    ):
        """记录一条管理操作审计日志。

        Parameters
        ----------
        admin_user : User
            执行操作的管理员用户对象
        action : str
            操作类型（见 AdminAuditLog.AUDIT_ACTIONS）
        target_type : str, optional
            目标类型（如 "user", "knowledge_file", "system"）
        target_id : str, optional
            目标 ID
        detail : str, optional
            操作详情（不包含密码、JWT、API Key、知识库正文）
        ip_address : str, optional
            客户端 IP
        user_agent : str, optional
            客户端 User-Agent
        module : str, optional
            模块分类（自动推断）
        status : str
            状态: success | failed | warning
        """
        try:
            self.repo.create(
                admin_id=admin_user.id,
                admin_username=admin_user.username,
                action=action,
                module=module,
                target_type=target_type,
                target_id=target_id,
                status=status,
                detail=detail,
                ip_address=ip_address,
                user_agent=user_agent,
            )
        except Exception as e:
            # 审计日志失败不应影响主业务
            logger.warning("审计日志记录失败: %s", e)
