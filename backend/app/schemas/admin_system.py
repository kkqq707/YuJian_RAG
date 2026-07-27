"""管理员系统管理 — 请求与响应模型"""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


# ---------------------------------------------------------------------------
# 系统状态
# ---------------------------------------------------------------------------


class ComponentStatus(BaseModel):
    """单个组件状态。"""

    status: str = Field(..., description="状态: ok | error | not_found | not_configured")
    detail: Optional[str] = Field(None, description="详细信息")
    model_name: Optional[str] = Field(None, description="Embedding 模型名称")
    model_path: Optional[str] = Field(None, description="Embedding 模型路径")
    load_method: Optional[str] = Field(None, description="Embedding 加载方式")
    strategy: Optional[str] = Field(None, description="Embedding 加载策略")


class AdminSystemStatusResponse(BaseModel):
    """管理员系统状态响应 — 完整的系统诊断信息。"""

    success: bool = Field(True, description="请求是否成功")
    version: str = Field(..., description="API 版本")
    overall_status: str = Field(..., description="整体状态: ok | degraded | error")

    # 各组件状态
    embedding: ComponentStatus = Field(..., description="Embedding 模型状态")
    deepseek: ComponentStatus = Field(..., description="DeepSeek / LLM 状态")
    chroma: ComponentStatus = Field(..., description="Chroma 向量库状态")
    sqlite: ComponentStatus = Field(..., description="SQLite 数据库状态")

    # 统计
    stats: "SystemStats" = Field(..., description="系统统计信息")


class SystemStats(BaseModel):
    """系统统计信息。"""

    total_files: int = Field(0, description="知识库文件总数")
    indexed_files: int = Field(0, description="已索引文件数")
    total_chunks: int = Field(0, description="知识库总片段数")
    chroma_vectors: int = Field(0, description="Chroma 向量数")
    total_users: int = Field(0, description="用户总数")
    active_users: int = Field(0, description="活跃用户数")
    admin_users: int = Field(0, description="管理员数量")
    today_questions: int = Field(0, description="今日问答数")
    recent_uploads: list[dict] = Field(default_factory=list, description="最近上传文件")
    embedding_model: str = Field("", description="Embedding 模型名称")
    embedding_model_path: str = Field("", description="Embedding 模型本地路径")
    embedding_load_method: str = Field("", description="Embedding 加载方式")
    chroma_collection: str = Field("", description="Chroma 集合名称")
    llm_provider: Optional[str] = Field(None, description="LLM 提供商")
    model_name: Optional[str] = Field(None, description="当前使用的模型名称（来自 AI 服务配置中心）")
    last_index_update: Optional[str] = Field(None, description="最后索引更新时间")


# ---------------------------------------------------------------------------
# 审计日志
# ---------------------------------------------------------------------------


class AuditLogItem(BaseModel):
    """审计日志条目。"""

    id: int = Field(..., description="日志 ID")
    admin_id: int = Field(..., description="管理员 ID")
    admin_username: str = Field(..., description="管理员用户名")
    action: str = Field(..., description="操作类型")
    target_type: Optional[str] = Field(None, description="目标类型")
    target_id: Optional[str] = Field(None, description="目标 ID")
    detail: Optional[str] = Field(None, description="操作详情")
    ip_address: Optional[str] = Field(None, description="客户端 IP")
    created_at: Optional[str] = Field(None, description="操作时间")

    model_config = ConfigDict(from_attributes=True)


class AuditLogResponse(BaseModel):
    """审计日志列表响应。"""

    success: bool = Field(True, description="请求是否成功")
    total: int = Field(..., description="总记录数")
    logs: list[AuditLogItem] = Field(default_factory=list, description="日志列表")


# ---------------------------------------------------------------------------
# 备份与恢复
# ---------------------------------------------------------------------------


class BackupResponse(BaseModel):
    """备份操作响应。"""

    success: bool = Field(..., description="备份是否成功")
    file_name: Optional[str] = Field(None, description="备份文件名")
    file_size_bytes: Optional[int] = Field(None, description="文件大小（字节）")
    file_size_mb: Optional[float] = Field(None, description="文件大小（MB）")
    created_at: Optional[str] = Field(None, description="创建时间")
    included: dict = Field(default_factory=dict, description="已备份的项目")
    error: Optional[str] = Field(None, description="错误信息")


class BackupListItem(BaseModel):
    """备份列表项。"""

    file_name: str = Field(..., description="备份文件名")
    file_size_bytes: int = Field(0, description="文件大小（字节）")
    file_size_mb: float = Field(0.0, description="文件大小（MB）")
    created_at: Optional[str] = Field(None, description="创建时间")


class BackupListResponse(BaseModel):
    """备份列表响应。"""

    success: bool = Field(True, description="请求是否成功")
    backups: list[BackupListItem] = Field(default_factory=list, description="备份列表")


class BackupStatusInfo(BaseModel):
    """备份状态信息。"""

    last_backup_time: Optional[str] = Field(None, description="最后备份时间")
    last_backup_size_bytes: int = Field(0, description="最后备份大小（字节）")
    last_backup_file: Optional[str] = Field(None, description="最后备份文件名")
    total_backups: int = Field(0, description="备份总数")
    total_backups_size_bytes: int = Field(0, description="备份总大小（字节）")
    status: str = Field("no_backup", description="备份状态: ok | no_backup")


class RestoreRequest(BaseModel):
    """恢复请求。"""

    file_name: str = Field(..., description="要恢复的备份文件名")
    targets: Optional[list[str]] = Field(
        None,
        description="恢复目标: database, chroma, uploads。默认全部恢复。",
    )


class RestoreResponse(BaseModel):
    """恢复响应。"""

    success: bool = Field(..., description="恢复是否成功")
    restored: list[str] = Field(default_factory=list, description="已恢复的项目")
    errors: list[str] = Field(default_factory=list, description="错误信息")
