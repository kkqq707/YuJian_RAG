"""通用数据模型 — request_id, 错误响应等"""

from __future__ import annotations

from pydantic import BaseModel, Field


class ErrorDetail(BaseModel):
    """统一错误详情。"""

    code: str = Field(..., description="错误码")
    message: str = Field(..., description="人类可读的错误消息")
    request_id: str = Field(..., description="请求追踪 ID")
