"""FastAPI 依赖注入 — request_id 中间件等

- 每个请求生成唯一的 request_id
- 安全响应头
- 不在此处初始化重模型
"""

from __future__ import annotations

import time
import uuid

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response


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


class RequestIDMiddleware(BaseHTTPMiddleware):
    """为每个请求添加唯一的 request_id。

    - 检查 X-Request-ID 请求头
    - 如果没有则生成 UUID
    - 响应中也添加 X-Request-ID 头
    """

    async def dispatch(self, request: Request, call_next):
        request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
        request.state.request_id = request_id

        response: Response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        return response


class RequestTimingMiddleware(BaseHTTPMiddleware):
    """请求耗时中间件 — 在响应头中记录处理时间。"""

    async def dispatch(self, request: Request, call_next):
        t0 = time.perf_counter()
        response: Response = await call_next(request)
        elapsed = time.perf_counter() - t0
        response.headers["X-Process-Time-Seconds"] = f"{elapsed:.3f}"
        return response
