"""管理员操作审计日志模型

记录管理员关键操作:
- 上传/删除知识库文件
- 管理员登录
- 重建索引
- 新增/删除用户
- 重置密码
- 修改角色
- 修改 LLM/AI 配置
- 系统设置变更

安全要求:
- 不得记录密码
- 不得记录 JWT / API Key
- 不得记录知识库正文
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, Integer, String, Text

from backend.app.models.base import Base


# ---------------------------------------------------------------------------
# 允许的操作类型
# ---------------------------------------------------------------------------
AUDIT_ACTIONS = {
    "admin_login",
    "file_upload",
    "file_delete",
    "file_index",
    "index_rebuild",
    "user_create",
    "user_delete",
    "user_disable",
    "user_enable",
    "user_update",
    "user_role_change",
    "user_password_reset",
    "login_success",
    "login_failed",
    "logout",
    "llm_config_update",
    "llm_connection_test",
    "model_switch",
    "system_setting_update",
    "jwt_regenerate",
}

# ---------------------------------------------------------------------------
# 模块分类
# ---------------------------------------------------------------------------
AUDIT_MODULES = {
    "user_management": "用户管理",
    "knowledge_base": "知识库",
    "ai_service": "AI服务",
    "chat": "聊天",
    "system": "系统",
}

# 操作 -> 模块 映射
ACTION_MODULE_MAP = {
    "admin_login": "system",
    "login_success": "system",
    "login_failed": "system",
    "logout": "system",
    "file_upload": "knowledge_base",
    "file_delete": "knowledge_base",
    "file_index": "knowledge_base",
    "index_rebuild": "knowledge_base",
    "user_create": "user_management",
    "user_delete": "user_management",
    "user_disable": "user_management",
    "user_enable": "user_management",
    "user_update": "user_management",
    "user_role_change": "user_management",
    "user_password_reset": "user_management",
    "llm_config_update": "ai_service",
    "llm_connection_test": "ai_service",
    "model_switch": "ai_service",
    "system_setting_update": "system",
    "jwt_regenerate": "system",
}


class AdminAuditLog(Base):
    """管理员操作审计日志。"""

    __tablename__ = "admin_audit_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    admin_id = Column(Integer, nullable=False, index=True)
    admin_username = Column(String(150), nullable=False)
    action = Column(String(50), nullable=False, index=True)
    module = Column(String(50), nullable=True, index=True)
    target_type = Column(String(50), nullable=True)
    target_id = Column(String(255), nullable=True)
    status = Column(String(20), nullable=True, default="success")
    detail = Column(Text, nullable=True)
    ip_address = Column(String(45), nullable=True)
    user_agent = Column(String(512), nullable=True)
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    def __repr__(self) -> str:
        return (
            f"AdminAuditLog(id={self.id}, admin={self.admin_username!r}, "
            f"action={self.action!r}, module={self.module!r}, target={self.target_type!r})"
        )
