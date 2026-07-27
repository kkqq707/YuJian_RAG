"""统一异常处理 — 业务异常与全局异常处理器

- 记录完整 traceback 到日志（不向用户暴露）
- 不返回原始异常对象
- 不泄露 API Key
- 不返回绝对路径
- 统一错误响应格式
"""

from __future__ import annotations

import logging
import traceback
import uuid
from typing import Optional

from fastapi import Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# 业务异常类
# ---------------------------------------------------------------------------


class AppException(Exception):
    """应用基础异常。"""

    def __init__(self, code: str, message: str, status_code: int = 500):
        self.code = code
        self.message = message
        self.status_code = status_code
        super().__init__(message)


class ValidationException(AppException):
    """请求校验异常。"""

    def __init__(self, message: str):
        super().__init__(code="VALIDATION_ERROR", message=message, status_code=422)


class RAGUnavailableException(AppException):
    """RAG 服务不可用异常。"""

    def __init__(self, message: str = "问答服务暂不可用，请稍后重试。"):
        super().__init__(code="RAG_UNAVAILABLE", message=message, status_code=503)


class VectorStoreNotFoundException(AppException):
    """向量库不存在异常。"""

    def __init__(self, message: str = "知识库尚未构建，请联系管理员。"):
        super().__init__(
            code="VECTOR_STORE_NOT_FOUND", message=message, status_code=503
        )


class LLMServiceException(AppException):
    """LLM 服务异常。"""

    def __init__(self, message: str = "大模型服务异常，请稍后重试。"):
        super().__init__(code="LLM_SERVICE_ERROR", message=message, status_code=503)


# ---------------------------------------------------------------------------
# 错误响应格式
# ---------------------------------------------------------------------------


def _build_error_response(
    code: str,
    message: str,
    status_code: int,
    request_id: str = "",
) -> JSONResponse:
    """构建统一错误响应。"""
    return JSONResponse(
        status_code=status_code,
        content={
            "success": False,
            "error": {
                "code": code,
                "message": message,
                "request_id": request_id or str(uuid.uuid4()),
            },
        },
    )


# ---------------------------------------------------------------------------
# 全局异常处理器注册
# ---------------------------------------------------------------------------


def register_exception_handlers(app):
    """向 FastAPI 应用注册全局异常处理器。"""

    @app.exception_handler(AppException)
    async def app_exception_handler(request: Request, exc: AppException) -> JSONResponse:
        request_id = getattr(request.state, "request_id", str(uuid.uuid4()))
        return _build_error_response(
            code=exc.code,
            message=exc.message,
            status_code=exc.status_code,
            request_id=request_id,
        )

    @app.exception_handler(StarletteHTTPException)
    async def http_exception_handler(
        request: Request, exc: StarletteHTTPException
    ) -> JSONResponse:
        request_id = getattr(request.state, "request_id", str(uuid.uuid4()))
        # 统一常见 HTTP 状态的错误码
        code_map = {
            401: "INVALID_CREDENTIALS",
            403: "FORBIDDEN",
            404: "NOT_FOUND",
            405: "METHOD_NOT_ALLOWED",
            422: "VALIDATION_ERROR",
            423: "ACCOUNT_LOCKED",
            429: "RATE_LIMITED",
        }
        code = code_map.get(exc.status_code, "HTTP_ERROR")
        return _build_error_response(
            code=code,
            message=str(exc.detail),
            status_code=exc.status_code,
            request_id=request_id,
        )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        request_id = getattr(request.state, "request_id", str(uuid.uuid4()))
        # 提取第一条校验错误
        detail = "请求参数校验失败"
        if exc.errors():
            first = exc.errors()[0]
            field = " → ".join(str(loc) for loc in first.get("loc", []))
            msg = first.get("msg", "")
            detail = f"{field}: {msg}" if field else msg
        return _build_error_response(
            code="VALIDATION_ERROR",
            message=detail,
            status_code=422,
            request_id=request_id,
        )

    @app.exception_handler(Exception)
    async def generic_exception_handler(
        request: Request, exc: Exception
    ) -> JSONResponse:
        request_id = getattr(request.state, "request_id", str(uuid.uuid4()))
        # 记录完整 traceback 到日志，便于排查
        logger.error(
            "未处理异常 | request_id=%s | %s: %s\n%s",
            request_id,
            type(exc).__name__,
            str(exc)[:200],
            traceback.format_exc(),
        )
        # 返回安全的错误消息（不暴露 traceback）
        return _build_error_response(
            code="INTERNAL_ERROR",
            message=f"服务器内部错误: {str(exc)[:200]}",
            status_code=500,
            request_id=request_id,
        )
