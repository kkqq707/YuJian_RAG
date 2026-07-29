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

    # ---- Phase 6: 推理异常处理器 ----
    try:
        from backend.app.services.inference_runtime import (
            InferenceQueueTimeoutError,
            InferenceExecutionTimeoutError,
            InferenceUnavailableError,
            UserRequestLimitError,
        )

        @app.exception_handler(InferenceQueueTimeoutError)
        async def inference_queue_timeout_handler(
            request: Request, exc: InferenceQueueTimeoutError,
        ) -> JSONResponse:
            request_id = getattr(request.state, "request_id", str(uuid.uuid4()))
            logger.warning(
                "推理排队超时 | request_id=%s resource=%s waited_ms=%.0f",
                request_id, exc.resource, exc.waited_ms,
            )
            return _build_error_response(
                code="INFERENCE_QUEUE_TIMEOUT",
                message="当前问答请求较多，请稍后重试",
                status_code=503,
                request_id=request_id,
            )

        @app.exception_handler(InferenceExecutionTimeoutError)
        async def inference_execution_timeout_handler(
            request: Request, exc: InferenceExecutionTimeoutError,
        ) -> JSONResponse:
            request_id = getattr(request.state, "request_id", str(uuid.uuid4()))
            logger.warning(
                "推理执行超时 | request_id=%s resource=%s elapsed_ms=%.0f",
                request_id, exc.resource, exc.elapsed_ms,
            )
            return _build_error_response(
                code="INFERENCE_EXECUTION_TIMEOUT",
                message="本次处理超时，请缩短问题或稍后重试",
                status_code=504,
                request_id=request_id,
            )

        @app.exception_handler(InferenceUnavailableError)
        async def inference_unavailable_handler(
            request: Request, exc: InferenceUnavailableError,
        ) -> JSONResponse:
            request_id = getattr(request.state, "request_id", str(uuid.uuid4()))
            logger.error(
                "推理服务不可用 | request_id=%s resource=%s detail=%s",
                request_id, exc.resource, exc.detail,
            )
            return _build_error_response(
                code="INFERENCE_UNAVAILABLE",
                message="模型服务暂不可用，请稍后重试或联系管理员",
                status_code=503,
                request_id=request_id,
            )

        @app.exception_handler(UserRequestLimitError)
        async def user_request_limit_handler(
            request: Request, exc: UserRequestLimitError,
        ) -> JSONResponse:
            request_id = getattr(request.state, "request_id", str(uuid.uuid4()))
            logger.info("用户请求超限 | request_id=%s", request_id)
            return _build_error_response(
                code="USER_REQUEST_LIMIT",
                message="当前已有回答正在生成，请稍候。",
                status_code=429,
                request_id=request_id,
            )

    except ImportError:
        pass  # InferenceRuntime 模块尚未加载时跳过

    # ---- Phase 7: 数据库与向量库异常处理器 ----

    try:
        from backend.app.db_retry import DatabaseBusyError

        @app.exception_handler(DatabaseBusyError)
        async def database_busy_handler(
            request: Request, exc: DatabaseBusyError,
        ) -> JSONResponse:
            request_id = getattr(request.state, "request_id", str(uuid.uuid4()))
            logger.warning("数据库繁忙 | request_id=%s", request_id)
            return _build_error_response(
                code="DATABASE_BUSY",
                message=exc.message,
                status_code=503,
                request_id=request_id,
            )

    except ImportError:
        pass

    try:
        from backend.app.vector_store_runtime import (
            VectorStoreBusyError,
            VectorStoreOperationError,
            DuplicateOperationError,
        )

        @app.exception_handler(VectorStoreBusyError)
        async def vector_store_busy_handler(
            request: Request, exc: VectorStoreBusyError,
        ) -> JSONResponse:
            request_id = getattr(request.state, "request_id", str(uuid.uuid4()))
            logger.warning("向量库繁忙 | request_id=%s", request_id)
            return _build_error_response(
                code="VECTOR_STORE_BUSY",
                message=exc.message,
                status_code=503,
                request_id=request_id,
            )

        @app.exception_handler(VectorStoreOperationError)
        async def vector_store_operation_error_handler(
            request: Request, exc: VectorStoreOperationError,
        ) -> JSONResponse:
            request_id = getattr(request.state, "request_id", str(uuid.uuid4()))
            logger.error("向量库操作失败 | request_id=%s", request_id)
            return _build_error_response(
                code="VECTOR_STORE_OPERATION_FAILED",
                message=exc.message,
                status_code=503,
                request_id=request_id,
            )

        @app.exception_handler(DuplicateOperationError)
        async def duplicate_operation_handler(
            request: Request, exc: DuplicateOperationError,
        ) -> JSONResponse:
            request_id = getattr(request.state, "request_id", str(uuid.uuid4()))
            logger.info("重复操作 | request_id=%s", request_id)
            return _build_error_response(
                code="DUPLICATE_OPERATION",
                message=exc.message,
                status_code=409,
                request_id=request_id,
            )

    except ImportError:
        pass

    # ---- Phase 9: 限流异常处理器 ----
    try:
        from backend.app.rate_limiter import RateLimitExceeded
        from backend.app.metrics import get_metrics

        @app.exception_handler(RateLimitExceeded)
        async def rate_limit_exceeded_handler(
            request: Request, exc: RateLimitExceeded,
        ) -> JSONResponse:
            request_id = getattr(request.state, "request_id", str(uuid.uuid4()))
            # 更新指标
            try:
                metrics = get_metrics()
                metrics.inc_rate_limited(category="")
                # 根据路径推断限流类别
                path = request.url.path
                if "/auth/login" in path:
                    metrics.inc_rate_limited(category="login")
                elif "/chat" in path:
                    metrics.inc_rate_limited(category="chat")
                elif "/upload" in path or "/files/upload" in path:
                    metrics.inc_rate_limited(category="upload")
            except Exception:
                pass

            logger.info(
                "rate_limited | request_id=%s rule=%s retry_after=%d",
                request_id, exc.rule_name, exc.retry_after,
            )

            response = JSONResponse(
                status_code=429,
                content={
                    "detail": exc.message,
                    "code": exc.code,
                    "retry_after": exc.retry_after,
                    "request_id": request_id,
                },
                headers={
                    "Retry-After": str(exc.retry_after),
                    "X-Request-ID": request_id,
                },
            )
            # 标记为 rate_limited
            request.state.rate_limited = True
            return response

    except ImportError:
        pass

    @app.exception_handler(Exception)
    async def generic_exception_handler(
        request: Request, exc: Exception
    ) -> JSONResponse:
        request_id = getattr(request.state, "request_id", str(uuid.uuid4()))
        # 客户端取消不记录为 500
        exc_name = type(exc).__name__
        if "ClientDisconnect" in exc_name or "cancel" in str(exc).lower():
            logger.info(
                "客户端取消 | request_id=%s | %s",
                request_id, exc_name,
            )
            return _build_error_response(
                code="CLIENT_DISCONNECT",
                message="请求已取消",
                status_code=499,
                request_id=request_id,
            )

        # 记录完整 traceback 到日志，便于排查
        logger.error(
            "未处理异常 | request_id=%s | %s: %s\n%s",
            request_id,
            exc_name,
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
