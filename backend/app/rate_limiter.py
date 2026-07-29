"""API 限流器 — 基于滑动窗口的内存限流

特性:
- 按 IP + user_id 组合限流（认证端点）
- 按 IP 限流（登录等公开端点）
- 读取类接口额度较高，写入类接口额度较低
- 健康检查可豁免
- 滑动窗口算法，精确控制时间窗口内的请求数

安全:
- 不暴露内部计数器细节
- 不暴露其他用户状态
- 限流异常不记录为 ERROR

注意：单进程内存限流，进程重启后归零。未来可迁移到 Redis。
"""

from __future__ import annotations

import logging
import time
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Optional

from backend.app.config import get_settings

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# 限流配置
# ---------------------------------------------------------------------------

@dataclass
class RateLimitRule:
    """限流规则"""
    max_requests: int      # 窗口内最大请求数
    window_seconds: int    # 滑动窗口大小（秒）
    description: str = ""  # 规则描述


def _get_rules_from_config() -> dict[str, RateLimitRule]:
    """从配置构建限流规则。"""
    try:
        settings = get_settings()
    except Exception:
        settings = None

    def _get(name: str, default: int) -> int:
        if settings:
            return getattr(settings, name, default)
        return default

    return {
        # ---- 认证相关 ----
        "auth_login": RateLimitRule(
            max_requests=_get("RATE_LIMIT_LOGIN_PER_MINUTE", 10),
            window_seconds=60,
            description="登录限流",
        ),
        "auth_refresh": RateLimitRule(
            max_requests=_get("RATE_LIMIT_REFRESH_PER_MINUTE", 20),
            window_seconds=60,
            description="Token 刷新限流",
        ),

        # ---- 普通用户聊天 ----
        "chat_user": RateLimitRule(
            max_requests=_get("RATE_LIMIT_CHAT_USER_PER_MINUTE", 30),
            window_seconds=60,
            description="普通用户聊天限流",
        ),
        "chat_user_message": RateLimitRule(
            max_requests=_get("RATE_LIMIT_CHAT_MESSAGE_PER_MINUTE", 20),
            window_seconds=60,
            description="普通用户发送消息限流",
        ),

        # ---- 管理员读取接口（高额度）----
        "admin_read": RateLimitRule(
            max_requests=_get("RATE_LIMIT_ADMIN_READ_PER_MINUTE", 200),
            window_seconds=60,
            description="管理员读取限流",
        ),

        # ---- 管理员写入接口（低额度）----
        "admin_write": RateLimitRule(
            max_requests=_get("RATE_LIMIT_ADMIN_WRITE_PER_MINUTE", 30),
            window_seconds=60,
            description="管理员写入限流",
        ),

        # ---- 管理员轮询接口（防止过快轮询）----
        "admin_poll": RateLimitRule(
            max_requests=_get("RATE_LIMIT_ADMIN_POLL_PER_MINUTE", 20),
            window_seconds=60,
            description="管理员轮询限流（日志列表、任务列表等）",
        ),

        # ---- 文档上传 ----
        "upload": RateLimitRule(
            max_requests=_get("RATE_LIMIT_UPLOAD_PER_MINUTE", 10),
            window_seconds=60,
            description="文件上传限流",
        ),

        # ---- 健康检查（高额度）----
        "health": RateLimitRule(
            max_requests=_get("RATE_LIMIT_HEALTH_PER_MINUTE", 300),
            window_seconds=60,
            description="健康检查限流（高额度）",
        ),

        # ---- 系统监控 ----
        "system_monitor": RateLimitRule(
            max_requests=30, window_seconds=60,
            description="系统监控限流",
        ),
    }


# 延迟初始化的规则缓存
_rules_cache: Optional[dict[str, RateLimitRule]] = None


def get_rules() -> dict[str, RateLimitRule]:
    """获取限流规则（延迟初始化，首次调用时从配置读取）。"""
    global _rules_cache
    if _rules_cache is None:
        _rules_cache = _get_rules_from_config()
    return _rules_cache


# ---------------------------------------------------------------------------
# 限流异常
# ---------------------------------------------------------------------------

class RateLimitExceeded(Exception):
    """限流异常 — 由中间件/依赖捕获并转换为 429 响应。

    不在日志中记录为 ERROR，使用 WARNING 或 INFO。
    """

    def __init__(
        self,
        message: str = "请求过于频繁，请稍后重试",
        retry_after: int = 30,
        code: str = "RATE_LIMITED",
        rule_name: str = "",
    ):
        self.message = message
        self.retry_after = retry_after
        self.code = code
        self.rule_name = rule_name
        super().__init__(message)


# ---------------------------------------------------------------------------
# 滑动窗口限流器
# ---------------------------------------------------------------------------

class SlidingWindowRateLimiter:
    """基于滑动窗口的内存限流器。

    使用有序时间戳列表记录每次请求，每次检查时清理过期记录。
    内存占用与窗口内请求数成正比，受限流额度控制。
    """

    def __init__(self):
        # key -> list[float] (Unix timestamps)
        self._windows: dict[str, list[float]] = defaultdict(list)
        # 统计计数
        self._denied_count: dict[str, int] = defaultdict(int)  # key -> denied count
        self._last_cleanup: float = time.monotonic()
        self._cleanup_interval: float = 300.0  # 每 5 分钟清理过期 key

    def _cleanup_expired(self):
        """清理过期的窗口数据，释放内存。"""
        now = time.monotonic()
        if now - self._last_cleanup < self._cleanup_interval:
            return
        self._last_cleanup = now

        max_window = max(r.window_seconds for r in get_rules().values())
        cutoff = now - max_window - 10  # 额外 10 秒缓冲区

        expired_keys = []
        for key, timestamps in list(self._windows.items()):
            # 移除过期时间戳
            self._windows[key] = [ts for ts in timestamps if ts > cutoff]
            if not self._windows[key]:
                expired_keys.append(key)

        for key in expired_keys:
            del self._windows[key]
            if key in self._denied_count:
                del self._denied_count[key]

        if expired_keys:
            logger.debug("RateLimiter 清理 %d 个过期 key", len(expired_keys))

    def check(
        self,
        key: str,
        rule: RateLimitRule,
    ) -> tuple[bool, int]:
        """检查是否超出限流额度。

        Parameters
        ----------
        key : str
            限流 key（如 IP 或 IP:user_id）
        rule : RateLimitRule
            限流规则

        Returns
        -------
        tuple[bool, int]
            (是否允许, retry_after 秒数)
        """
        now = time.monotonic()
        cutoff = now - rule.window_seconds

        # 获取当前窗口
        timestamps = self._windows.get(key, [])

        # 过滤过期时间戳
        if timestamps and timestamps[0] < cutoff:
            timestamps = [ts for ts in timestamps if ts > cutoff]
            self._windows[key] = timestamps

        # 检查是否超限
        if len(timestamps) >= rule.max_requests:
            # 计算 retry_after: 最早记录过期后即可重试
            if timestamps:
                oldest = timestamps[0]
                retry_after = max(1, int(oldest + rule.window_seconds - now) + 1)
            else:
                retry_after = rule.window_seconds
            self._denied_count[key] += 1
            return False, retry_after

        # 未超限，记录本次请求
        timestamps.append(now)
        self._windows[key] = timestamps

        # 定期清理
        self._cleanup_expired()

        return True, 0

    def get_denied_count(self, key: str) -> int:
        """获取被拒绝次数（用于监控）。"""
        return self._denied_count.get(key, 0)

    def get_active_key_count(self) -> int:
        """获取活跃 key 数量。"""
        return len(self._windows)

    def get_total_denied(self) -> int:
        """获取总计拒绝次数。"""
        return sum(self._denied_count.values())


# ---------------------------------------------------------------------------
# 限流器工厂
# ---------------------------------------------------------------------------

# 全局单例
_limiter: Optional[SlidingWindowRateLimiter] = None


def get_rate_limiter() -> SlidingWindowRateLimiter:
    """获取全局限流器实例。"""
    global _limiter
    if _limiter is None:
        _limiter = SlidingWindowRateLimiter()
    return _limiter


def build_rate_limit_key(
    ip: str,
    user_id: Optional[int] = None,
    rule_name: str = "",
) -> str:
    """构建限流 key。

    - 认证端点: "{rule}:{ip}:{user_id}"
    - 公开端点: "{rule}:{ip}"

    不同用户/IP 的额度完全独立。
    """
    if user_id is not None:
        return f"{rule_name}:{ip}:{user_id}"
    return f"{rule_name}:{ip}"


# ---------------------------------------------------------------------------
# 便捷函数：在各端点依赖中调用
# ---------------------------------------------------------------------------

def check_rate_limit(
    ip: str,
    rule_name: str,
    user_id: Optional[int] = None,
) -> None:
    """检查限流，超限时抛出 RateLimitExceeded。

    Usage:
        check_rate_limit(client_ip, "auth_login")
        check_rate_limit(client_ip, "chat_user", current_user.id)
    """
    rule = get_rules().get(rule_name)
    if rule is None:
        logger.warning("未知限流规则: %s，放行", rule_name)
        return

    limiter = get_rate_limiter()
    key = build_rate_limit_key(ip, user_id, rule_name)
    allowed, retry_after = limiter.check(key, rule)

    if not allowed:
        logger.info(
            "限流触发 | rule=%s key_prefix=%s retry_after=%d",
            rule_name, key.rsplit(":", 1)[0] if ":" in key else key, retry_after,
        )
        raise RateLimitExceeded(
            message="请求过于频繁，请稍后重试",
            retry_after=retry_after,
            code="RATE_LIMITED",
            rule_name=rule_name,
        )
