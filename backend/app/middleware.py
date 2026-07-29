"""增强中间件 — 统一 request_id、访问日志、慢请求追踪

整合原有 dependencies.py 中的中间件并增强:
- RequestIDMiddleware: 验证客户端 X-Request-ID，防止日志注入
- AccessLogMiddleware: 结构化访问日志，敏感数据过滤
- 慢请求标记和告警
"""

from __future__ import annotations

import logging
import re
import time
import uuid
from typing import Optional

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

from backend.app.client_ip import get_client_ip
from backend.app.config import get_settings
from backend.app.metrics import get_metrics

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# 常量
# ---------------------------------------------------------------------------

_MAX_REQUEST_ID_LENGTH = 128
_REQUEST_ID_PATTERN = re.compile(r"^[a-zA-Z0-9\-_./]{1,128}$")

_SLOW_REQUEST_THRESHOLD_MS = 3000
_VERY_SLOW_REQUEST_THRESHOLD_MS = 10000

# 健康检查路径（降低日志频率）
_HEALTH_CHECK_PATHS = {
    "/health",
    "/api/v1/health",
}

# 轮询接口路径前缀（适度归一化路径，避免基数过高）
_POLL_PATH_PREFIXES = [
    "/api/v1/admin/document-tasks",
    "/api/v1/admin/logs",
    "/api/v1/admin/system/logs",
]

# 404 扫描路径前缀（降低日志级别）
_SCAN_PATH_PREFIXES = [
    "/wp-admin",
    "/wp-login",
    "/phpmyadmin",
    "/.env",
    "/adminer",
    "/actuator",
    "/api/v1/.env",
    "/.git",
]


# ---------------------------------------------------------------------------
# 请求 ID 验证
# ---------------------------------------------------------------------------

def _validate_request_id(raw: str) -> Optional[str]:
    """验证并清理客户端提供的 X-Request-ID。

    - 格式合法 → 保留
    - 不合法 → 返回 None（调用方生成新 UUID）
    - 防止换行和日志注入
    """
    if not raw:
        return None
    raw = raw.strip()
    if not raw:
        return None
    if len(raw) > _MAX_REQUEST_ID_LENGTH:
        return None
    if "\n" in raw or "\r" in raw:
        return None
    if not _REQUEST_ID_PATTERN.match(raw):
        return None
    return raw


# ---------------------------------------------------------------------------
# 路径归一化
# ---------------------------------------------------------------------------

def _normalize_path(path: str) -> str:
    """归一化 URL 路径，避免日志基数过高。

    - 数字 ID 替换为 {id}
    - UUID 替换为 {uuid}
    """
    import re as _re
    # UUID pattern
    normalized = _re.sub(
        r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}",
        "{uuid}",
        path,
    )
    # Numeric IDs in path segments
    normalized = _re.sub(r"/\d+/", "/{id}/", normalized)
    # Trailing numeric ID
    normalized = _re.sub(r"/\d+$", "/{id}", normalized)
    return normalized


def _is_health_check(path: str) -> bool:
    """检查是否为健康检查路径。"""
    return path in _HEALTH_CHECK_PATHS or path.rstrip("/") in _HEALTH_CHECK_PATHS


def _is_scan_path(path: str) -> bool:
    """检查是否为 404 扫描路径。"""
    for prefix in _SCAN_PATH_PREFIXES:
        if path.startswith(prefix):
            return True
    return False


def _should_throttle_health_log() -> bool:
    """健康检查日志节流：每 10 秒最多记录一条。"""
    now = time.monotonic()
    if not hasattr(_should_throttle_health_log, "_last"):
        _should_throttle_health_log._last = 0.0  # type: ignore[attr-defined]
    if now - _should_throttle_health_log._last < 10.0:  # type: ignore[attr-defined]
        return True
    _should_throttle_health_log._last = now  # type: ignore[attr-defined]
    return False


# ---------------------------------------------------------------------------
# Enhanced RequestIDMiddleware
# ---------------------------------------------------------------------------

class RequestIDMiddleware(BaseHTTPMiddleware):
    """增强的请求 ID 中间件。

    - 优先接受格式合法的客户端 X-Request-ID
    - 不合法时生成新的 UUID v4
    - 限制长度，防止换行和日志注入
    - 保存到 request.state.request_id
    - 响应头返回 X-Request-ID
    """

    async def dispatch(self, request: Request, call_next):
        raw = request.headers.get("X-Request-ID", "")
        request_id = _validate_request_id(raw)
        source = "client" if request_id else "generated"
        if not request_id:
            request_id = str(uuid.uuid4())

        # 保存到 request.state，供下游读取
        request.state.request_id = request_id
        request.state.request_id_source = source

        response: Response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        return response


# ---------------------------------------------------------------------------
# AccessLogMiddleware
# ---------------------------------------------------------------------------

class AccessLogMiddleware(BaseHTTPMiddleware):
    """结构化访问日志中间件。

    记录每个 HTTP 请求：
    - request_id, method, normalized_path, status_code, duration_ms
    - user_id (已认证时), client_ip, response_size
    - error_code, rate_limited, timestamp

    不记录：
    - query 中的 Token 或敏感参数
    - Authorization 头
    - 请求正文
    - 完整上传文件名
    """

    async def dispatch(self, request: Request, call_next):
        request_id = getattr(request.state, "request_id", str(uuid.uuid4()))
        t0 = time.perf_counter()

        # 记录活跃请求
        metrics = get_metrics()
        metrics.inc_requests_total()
        metrics.inc_requests_active()

        path = request.url.path
        method = request.method
        normalized_path = _normalize_path(path)

        # 解析客户端 IP
        client_ip, ip_source = get_client_ip(request)
        request.state.client_ip = client_ip
        request.state.client_ip_source = ip_source

        status_code = 500
        error_code: Optional[str] = None
        rate_limited = False
        response_size = 0
        cancelled = False

        try:
            response: Response = await call_next(request)
            status_code = response.status_code
            # 获取响应大小
            content_length = response.headers.get("content-length")
            if content_length and content_length.isdigit():
                response_size = int(content_length)
            elif hasattr(response, "body"):
                try:
                    response_size = len(response.body)
                except Exception:
                    pass
        except Exception as exc:
            # 客户端取消
            if "ClientDisconnect" in type(exc).__name__ or "cancel" in str(exc).lower():
                cancelled = True
                status_code = 499  # Nginx 风格：客户端取消
                metrics.inc_client_cancelled()
            raise
        finally:
            duration_ms = (time.perf_counter() - t0) * 1000
            metrics.dec_requests_active()
            metrics.record_status(status_code)
            metrics.record_duration(duration_ms)

            # 慢请求检测
            is_slow = duration_ms > _SLOW_REQUEST_THRESHOLD_MS
            is_very_slow = duration_ms > _VERY_SLOW_REQUEST_THRESHOLD_MS
            if is_slow:
                metrics.inc_slow_request(very_slow=is_very_slow)

            # 获取 user_id（从 request.state 或 auth 依赖设置的）
            user_id = getattr(request.state, "auth_user_id", None)

            # 构建日志条目
            log_data = {
                "request_id": request_id,
                "method": method,
                "normalized_path": normalized_path,
                "status_code": status_code,
                "duration_ms": round(duration_ms, 2),
                "user_id": user_id,
                "client_ip": client_ip,
                "response_size": response_size,
                "rate_limited": rate_limited,
                "slow": is_slow,
                "cancelled": cancelled,
            }
            if error_code:
                log_data["error_code"] = error_code

            # 健康检查日志节流
            if _is_health_check(path):
                if not _should_throttle_health_log():
                    logger.debug(
                        "access health | request_id=%s status=%d duration=%.1fms",
                        request_id, status_code, duration_ms,
                    )
                return response

            # 404 扫描请求降低级别
            if status_code == 404 and _is_scan_path(path):
                logger.debug(
                    "access 404 scan | request_id=%s method=%s path=%s ip=%s",
                    request_id, method, normalized_path, client_ip,
                )
                return response

            # 客户端取消不记为错误
            if cancelled:
                logger.info(
                    "access client_cancelled | request_id=%s method=%s path=%s duration=%.1fms",
                    request_id, method, normalized_path, duration_ms,
                )
                return response

            # 按状态码选择日志级别
            if status_code >= 500:
                logger.error(
                    "access 5xx | request_id=%s method=%s path=%s status=%d duration=%.1fms user=%s ip=%s",
                    request_id, method, normalized_path, status_code, duration_ms,
                    user_id, client_ip,
                )
            elif status_code >= 400:
                if status_code == 429:
                    logger.info(
                        "access rate_limited | request_id=%s method=%s path=%s duration=%.1fms user=%s ip=%s",
                        request_id, method, normalized_path, duration_ms,
                        user_id, client_ip,
                    )
                else:
                    logger.info(
                        "access 4xx | request_id=%s method=%s path=%s status=%d duration=%.1fms user=%s ip=%s",
                        request_id, method, normalized_path, status_code, duration_ms,
                        user_id, client_ip,
                    )
            else:
                # 慢请求告警
                if is_very_slow:
                    logger.warning(
                        "access very_slow | request_id=%s method=%s path=%s status=%d duration=%.1fms user=%s ip=%s",
                        request_id, method, normalized_path, status_code, duration_ms,
                        user_id, client_ip,
                    )
                elif is_slow:
                    logger.info(
                        "access slow | request_id=%s method=%s path=%s status=%d duration=%.1fms user=%s ip=%s",
                        request_id, method, normalized_path, status_code, duration_ms,
                        user_id, client_ip,
                    )
                else:
                    logger.info(
                        "access | request_id=%s method=%s path=%s status=%d duration=%.1fms user=%s ip=%s",
                        request_id, method, normalized_path, status_code, duration_ms,
                        user_id, client_ip,
                    )

        return response


# ---------------------------------------------------------------------------
# RequestTimingMiddleware
# ---------------------------------------------------------------------------

class RequestTimingMiddleware(BaseHTTPMiddleware):
    """请求耗时中间件 — 在响应头中记录处理时间。"""

    async def dispatch(self, request: Request, call_next):
        t0 = time.perf_counter()
        response: Response = await call_next(request)
        elapsed = time.perf_counter() - t0
        response.headers["X-Process-Time-Seconds"] = f"{elapsed:.3f}"
        return response


# ---------------------------------------------------------------------------
# SecurityHeadersMiddleware (from original dependencies.py)
# ---------------------------------------------------------------------------

class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """安全响应头中间件。

    为所有响应添加安全相关的 HTTP 头:
    - X-Content-Type-Options: nosniff
    - X-Frame-Options: DENY
    - Referrer-Policy: no-referrer
    - Permissions-Policy: 最小权限
    - Cache-Control: no-store（认证响应由路由层单独控制）
    """

    async def dispatch(self, request: Request, call_next):
        response: Response = await call_next(request)

        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["Permissions-Policy"] = (
            "camera=(), microphone=(), geolocation=(), "
            "interest-cohort=()"
        )

        # 认证相关端点设置 no-store
        path = request.url.path
        if any(
            endpoint in path
            for endpoint in ["/auth/login", "/auth/refresh", "/auth/me"]
        ):
            response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
            response.headers["Pragma"] = "no-cache"

        return response
