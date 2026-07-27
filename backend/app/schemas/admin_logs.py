"""系统日志 — 请求与响应模型"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


# ---------------------------------------------------------------------------
# 日志条目
# ---------------------------------------------------------------------------


class SystemLogItem(BaseModel):
    """系统日志条目。"""

    id: int = Field(..., description="日志 ID")
    user_id: Optional[int] = Field(None, description="用户 ID")
    username: str = Field("", description="用户名")
    module: Optional[str] = Field(None, description="模块")
    action: str = Field(..., description="操作")
    status: Optional[str] = Field("success", description="状态: success | failed | warning")
    target_type: Optional[str] = Field(None, description="目标类型")
    target_id: Optional[str] = Field(None, description="目标 ID")
    detail: Optional[str] = Field(None, description="操作详情")
    ip_address: Optional[str] = Field(None, description="客户端 IP")
    created_at: Optional[str] = Field(None, description="操作时间")

    model_config = ConfigDict(from_attributes=True)


class SystemLogDetail(BaseModel):
    """系统日志详情。"""

    id: int = Field(..., description="日志 ID")
    user_id: Optional[int] = Field(None, description="用户 ID")
    username: str = Field("", description="用户名")
    module: Optional[str] = Field(None, description="模块")
    action: str = Field(..., description="操作")
    status: Optional[str] = Field("success", description="状态")
    target_type: Optional[str] = Field(None, description="目标类型")
    target_id: Optional[str] = Field(None, description="目标 ID")
    detail: Optional[str] = Field(None, description="操作详情")
    ip_address: Optional[str] = Field(None, description="客户端 IP")
    user_agent: Optional[str] = Field(None, description="User-Agent")
    created_at: Optional[str] = Field(None, description="操作时间")

    model_config = ConfigDict(from_attributes=True)


class SystemLogListResponse(BaseModel):
    """系统日志列表响应。"""

    success: bool = Field(True, description="请求是否成功")
    total: int = Field(..., description="总记录数")
    items: list[SystemLogItem] = Field(default_factory=list, description="日志列表")


# ---------------------------------------------------------------------------
# 健康检查
# ---------------------------------------------------------------------------


class HealthCheckResponse(BaseModel):
    """系统健康检查响应。"""

    success: bool = Field(True, description="请求是否成功")
    backend: bool = Field(..., description="Backend API 状态")
    database: bool = Field(..., description="Database 状态")
    chroma: bool = Field(..., description="Chroma Vector DB 状态")
    chroma_detail: str = Field("", description="Chroma 详细状态信息")
    llm: bool = Field(..., description="LLM API 状态")
    embedding: bool = Field(..., description="Embedding 模型状态")


# ---------------------------------------------------------------------------
# 系统设置
# ---------------------------------------------------------------------------


class SystemSettingItem(BaseModel):
    """系统设置项。"""

    id: int = Field(..., description="ID")
    key: str = Field(..., description="设置键")
    value: str = Field("", description="设置值")
    type: str = Field("string", description="值类型")
    description: Optional[str] = Field(None, description="说明")

    model_config = ConfigDict(from_attributes=True)


class SystemSettingsResponse(BaseModel):
    """系统设置列表响应。"""

    success: bool = Field(True)
    settings: dict = Field(default_factory=dict, description="设置键值对")


class SaveSettingRequest(BaseModel):
    """保存设置请求。"""

    key: str = Field(..., description="设置键")
    value: str = Field(..., description="设置值")


class SaveSettingsBulkRequest(BaseModel):
    """批量保存设置请求。"""

    settings: dict = Field(..., description="设置键值对")


class SystemInfoResponse(BaseModel):
    """系统信息响应。"""

    success: bool = Field(True)
    app_name: str = Field("企业智库 AI")
    version: str = Field("v1.0.0")
    deploy_mode: str = Field("单企业版")
    database_type: str = Field("SQLite")
    vector_store: str = Field("Chroma")
    model_name: Optional[str] = Field(None, description="当前使用的模型名称（来自 AI 服务配置中心）")


class SecuritySettingsResponse(BaseModel):
    """安全设置响应。"""

    success: bool = Field(True)
    jwt_initialized: bool = Field(..., description="JWT 是否已初始化")
    jwt_algorithm: str = Field("HS256")
    access_token_expire_minutes: int = Field(30)
    refresh_token_expire_days: int = Field(7)
    encryption_configured: bool = Field(..., description="加密密钥是否已配置")


class JWTRegenResponse(BaseModel):
    """重新生成 JWT 密钥响应。"""

    success: bool = Field(True)
    message: str = Field(..., description="操作结果说明")
