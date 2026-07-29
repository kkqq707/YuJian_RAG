"""客户端 IP 解析 — 可信代理支持

规则:
1. 不直接信任任意客户端提交的 X-Forwarded-For
2. 仅在请求来自可信代理时读取转发头
3. IPv4 和 IPv6 都支持
4. 不将端口拼进 IP key
5. 不记录伪造的完整转发链

配置:
- TRUSTED_PROXIES: 可信代理 IP/网段列表（逗号分隔）
"""

from __future__ import annotations

import ipaddress
import logging
from typing import Optional

from fastapi import Request

from backend.app.config import get_settings

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# 可信代理配置
# ---------------------------------------------------------------------------

def _parse_trusted_proxies() -> set[str]:
    """解析可信代理列表。

    从环境变量 TRUSTED_PROXIES 读取（逗号分隔），
    支持 IP 地址和 CIDR 网段。
    Docker 内部 Nginx → backend 场景默认可信。
    """
    settings = get_settings()
    raw = getattr(settings, "TRUSTED_PROXIES", "")
    if not raw:
        # 默认：Docker 内部网段
        return {
            "172.16.0.0/12",
            "10.0.0.0/8",
            "127.0.0.1",
            "::1",
        }

    proxies = set()
    for item in raw.split(","):
        item = item.strip()
        if item:
            proxies.add(item)
    return proxies


def _is_trusted_proxy(host: str) -> bool:
    """检查 host 是否为可信代理。"""
    trusted = _parse_trusted_proxies()
    if not trusted:
        return False

    try:
        addr = ipaddress.ip_address(host)
    except ValueError:
        return False

    for proxy in trusted:
        try:
            network = ipaddress.ip_network(proxy, strict=False)
            if addr in network:
                return True
        except ValueError:
            # 单个 IP 地址
            if proxy == host:
                return True
    return False


# ---------------------------------------------------------------------------
# IP 解析
# ---------------------------------------------------------------------------

def get_client_ip(request: Request) -> tuple[str, str]:
    """解析真实客户端 IP。

    策略:
    1. 检查请求来源是否可信代理
    2. 若可信，从 X-Forwarded-For 取最左侧（原始客户端）IP
    3. 若不可信，使用 request.client.host
    4. 剥离端口号
    5. 支持 IPv4 和 IPv6

    Returns
    -------
    tuple[str, str]
        (IP 地址, 解析方式: "proxy" | "direct" | "fallback")
    """
    client = request.client
    direct_host = client.host if client else None

    # 检查是否来自可信代理
    if direct_host and _is_trusted_proxy(direct_host):
        # 从 X-Forwarded-For 获取原始客户端 IP
        forwarded = request.headers.get("X-Forwarded-For", "")
        if forwarded:
            # X-Forwarded-For 格式: client, proxy1, proxy2
            # 取最左侧（原始客户端）
            original = forwarded.split(",")[0].strip()

            # 剥离端口号
            original = _strip_port(original)

            # 验证格式
            if _is_valid_ip(original):
                return original, "proxy"

        # 可信代理但没有转发头 → 使用代理 IP
        if direct_host:
            return _strip_port(direct_host), "proxy_direct"
        return "127.0.0.1", "fallback"

    # 非可信代理 → 使用 request.client.host
    if direct_host:
        return _strip_port(direct_host), "direct"

    return "127.0.0.1", "fallback"


def _strip_port(host: str) -> str:
    """剥离 IPv4/IPv6 地址中的端口号。

    IPv4: "192.168.1.1:8080" → "192.168.1.1"
    IPv6: "[::1]:8080" → "::1"
    """
    if not host:
        return host

    # IPv6 带端口: [::1]:8080
    if host.startswith("["):
        idx = host.rfind("]")
        if idx > 0:
            return host[1:idx]
        return host

    # IPv4 带端口: 192.168.1.1:8080
    if ":" in host:
        # 检查是否是 IPv6（含多个冒号）
        parts = host.split(":")
        if len(parts) > 2:
            # IPv6 不带方括号，直接返回
            return host
        # IPv4 带端口，取第一部分
        return parts[0]

    return host


def _is_valid_ip(host: str) -> bool:
    """验证是否为合法 IP 地址。"""
    if not host:
        return False
    try:
        ipaddress.ip_address(host)
        return True
    except ValueError:
        return False
