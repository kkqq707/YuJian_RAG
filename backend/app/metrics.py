"""运行时指标 — 单进程内存指标

特性:
- 进程重启后归零
- 更新失败不影响请求
- 管理员状态接口可查看
- 普通用户不可查看详细指标
- 不暴露 IP 列表和用户名列表
"""

from __future__ import annotations

import threading
import time
from collections import defaultdict
from typing import Optional


class RuntimeMetrics:
    """线程安全的单进程内存指标收集器。"""

    def __init__(self):
        self._lock = threading.Lock()

        # ---- HTTP 请求计数 ----
        self.http_requests_total: int = 0
        self.http_requests_active: int = 0
        self.http_2xx_total: int = 0
        self.http_3xx_total: int = 0
        self.http_4xx_total: int = 0
        self.http_5xx_total: int = 0

        # ---- 限流计数 ----
        self.rate_limited_total: int = 0
        self.login_rate_limited_total: int = 0
        self.chat_rate_limited_total: int = 0
        self.upload_rate_limited_total: int = 0

        # ---- 慢请求 ----
        self.slow_request_total: int = 0       # > SLOW_REQUEST_THRESHOLD_MS
        self.very_slow_request_total: int = 0  # > VERY_SLOW_REQUEST_THRESHOLD_MS

        # ---- 请求耗时 ----
        self._request_duration_sum_ms: float = 0.0
        self._request_duration_max_ms: float = 0.0
        self._request_duration_count: int = 0

        # ---- 客户端取消 ----
        self.client_cancelled_total: int = 0

        # ---- 外部 LLM 错误 ----
        self.llm_429_total: int = 0
        self.llm_5xx_total: int = 0

    def inc_requests_total(self):
        with self._lock:
            self.http_requests_total += 1

    def inc_requests_active(self):
        with self._lock:
            self.http_requests_active += 1

    def dec_requests_active(self):
        with self._lock:
            self.http_requests_active = max(0, self.http_requests_active - 1)

    def record_status(self, status_code: int):
        with self._lock:
            if 200 <= status_code < 300:
                self.http_2xx_total += 1
            elif 300 <= status_code < 400:
                self.http_3xx_total += 1
            elif 400 <= status_code < 500:
                self.http_4xx_total += 1
            elif status_code >= 500:
                self.http_5xx_total += 1

    def record_duration(self, duration_ms: float):
        with self._lock:
            self._request_duration_sum_ms += duration_ms
            self._request_duration_max_ms = max(
                self._request_duration_max_ms, duration_ms
            )
            self._request_duration_count += 1

    def inc_rate_limited(self, category: str = ""):
        with self._lock:
            self.rate_limited_total += 1
            if category == "login":
                self.login_rate_limited_total += 1
            elif category == "chat":
                self.chat_rate_limited_total += 1
            elif category == "upload":
                self.upload_rate_limited_total += 1

    def inc_slow_request(self, very_slow: bool = False):
        with self._lock:
            self.slow_request_total += 1
            if very_slow:
                self.very_slow_request_total += 1

    def inc_client_cancelled(self):
        with self._lock:
            self.client_cancelled_total += 1

    def inc_llm_429(self):
        with self._lock:
            self.llm_429_total += 1

    def inc_llm_5xx(self):
        with self._lock:
            self.llm_5xx_total += 1

    @property
    def request_duration_average_ms(self) -> float:
        with self._lock:
            if self._request_duration_count == 0:
                return 0.0
            return self._request_duration_sum_ms / self._request_duration_count

    @property
    def request_duration_max_ms(self) -> float:
        with self._lock:
            return self._request_duration_max_ms

    def snapshot(self) -> dict:
        """返回当前指标快照（线程安全）。

        注意：不暴露 IP 列表、用户名列表。
        """
        with self._lock:
            return {
                "http_requests_total": self.http_requests_total,
                "http_requests_active": self.http_requests_active,
                "http_2xx_total": self.http_2xx_total,
                "http_3xx_total": self.http_3xx_total,
                "http_4xx_total": self.http_4xx_total,
                "http_5xx_total": self.http_5xx_total,
                "rate_limited_total": self.rate_limited_total,
                "login_rate_limited_total": self.login_rate_limited_total,
                "chat_rate_limited_total": self.chat_rate_limited_total,
                "upload_rate_limited_total": self.upload_rate_limited_total,
                "slow_request_total": self.slow_request_total,
                "very_slow_request_total": self.very_slow_request_total,
                "request_duration_average_ms": round(self.request_duration_average_ms, 2),
                "request_duration_max_ms": round(self.request_duration_max_ms, 2),
                "client_cancelled_total": self.client_cancelled_total,
                "llm_429_total": self.llm_429_total,
                "llm_5xx_total": self.llm_5xx_total,
            }


# 全局单例
_metrics: Optional[RuntimeMetrics] = None


def get_metrics() -> RuntimeMetrics:
    """获取全局指标实例。"""
    global _metrics
    if _metrics is None:
        _metrics = RuntimeMetrics()
    return _metrics
