"""管理员 API 配置 — 请求与响应模型

安全策略:
- 响应中不返回 API Key 明文
- 请求中 API Key 仅用于传输，不记录日志
- JWT Secret 不返回
"""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# LLM 配置
# ---------------------------------------------------------------------------


class LLMConfigRequest(BaseModel):
    """LLM 配置保存请求。"""

    provider: str = Field(
        default="openai-compatible",
        description="服务商标识",
        examples=["openai-compatible"],
    )
    base_url: str = Field(
        default="",
        description="API Base URL",
        examples=["https://api.deepseek.com/v1"],
    )
    api_key: str = Field(
        default="",
        description="API Key（明文传输，服务端加密存储）",
    )
    model: str = Field(
        default="",
        description="模型名称",
        examples=["deepseek-chat"],
    )
    enabled: bool = Field(
        default=True,
        description="是否启用",
    )


class LLMConfigResponse(BaseModel):
    """LLM 配置展示响应 — API Key 已脱敏。"""

    configured: bool = Field(False, description="是否已配置")
    id: Optional[int] = Field(None, description="配置 ID")
    provider: Optional[str] = Field(None, description="服务商标识")
    base_url: Optional[str] = Field(None, description="API Base URL")
    model: Optional[str] = Field(None, description="模型名称")
    enabled: bool = Field(False, description="是否启用")
    api_key_masked: Optional[str] = Field(None, description="脱敏后的 API Key")


# ---------------------------------------------------------------------------
# 测试连接
# ---------------------------------------------------------------------------


class TestConnectionRequest(BaseModel):
    """LLM 连接测试请求。"""

    base_url: str = Field(..., description="API Base URL")
    api_key: str = Field(..., description="API Key（明文）")
    model: str = Field(..., description="模型名称")


class TestConnectionResponse(BaseModel):
    """LLM 连接测试响应 — 不返回 API Key、Token、异常堆栈。"""

    success: bool = Field(..., description="连接是否成功")
    model: str = Field("", description="测试的模型名称")
    latency_ms: int = Field(0, description="响应延迟（毫秒）")
    response_preview: str = Field("", description="响应预览（最多 50 字符）")
    error: Optional[str] = Field(None, description="安全错误信息")


# ---------------------------------------------------------------------------
# 模型列表
# ---------------------------------------------------------------------------


class ModelItem(BaseModel):
    """可用模型条目。"""

    name: str = Field(..., description="模型名称")
    provider: str = Field("", description="提供商")


class ModelListResponse(BaseModel):
    """可用模型列表响应。"""

    success: bool = Field(True, description="请求是否成功")
    models: list[ModelItem] = Field(default_factory=list, description="可用模型列表")


# ---------------------------------------------------------------------------
# 安全状态
# ---------------------------------------------------------------------------


class SecurityStatusResponse(BaseModel):
    """安全状态响应 — 不返回 JWT Secret。"""

    jwt_initialized: bool = Field(..., description="JWT Secret 是否已初始化")
    encryption_configured: bool = Field(..., description="加密主密钥是否已配置")
    llm_configured: bool = Field(..., description="LLM 是否已配置")
