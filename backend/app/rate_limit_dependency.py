"""限流依赖注入 — FastAPI Depends 可复用组件

提供:
- rate_limit_admin_read(): 管理员 GET 接口限流
- rate_limit_admin_write(): 管理员 POST/PUT/PATCH/DELETE 接口限流
- rate_limit_admin_poll(): 管理员轮询接口限流
- rate_limit_upload(): 上传接口限流
- rate_limit_health(): 健康检查限流（高额度）
"""

from __future__ import annotations

from typing import Optional

from fastapi import Depends, Request

from backend.app.client_ip import get_client_ip
from backend.app.models.user import User
from backend.app.rate_limiter import check_rate_limit
from backend.app.security.dependencies import get_current_active_user


async def _get_ip_and_check(
    request: Request,
    rule_name: str,
    current_user: Optional[User] = None,
):
    """内部辅助：获取 IP 并检查限流。"""
    client_ip, _ = get_client_ip(request)
    user_id = current_user.id if current_user else None
    # 保存 user_id 供访问日志使用
    if user_id is not None:
        request.state.auth_user_id = user_id
    check_rate_limit(client_ip, rule_name, user_id)


def _make_rate_limit_dep(rule_name: str, require_auth: bool):
    """构建限流依赖函数（工厂）。"""

    async def _dep(
        request: Request,
        current_user: Optional[User] = Depends(
            get_current_active_user if require_auth else lambda: None
        ),
    ):
        await _get_ip_and_check(request, rule_name, current_user)

    return _dep


# ---- 预构建依赖 ----

# 管理员读取接口（GET，高额度）
rate_limit_admin_read = _make_rate_limit_dep("admin_read", require_auth=True)

# 管理员写入接口（POST/PUT/PATCH/DELETE，低额度）
rate_limit_admin_write = _make_rate_limit_dep("admin_write", require_auth=True)

# 管理员轮询接口（任务列表、日志列表等）
rate_limit_admin_poll = _make_rate_limit_dep("admin_poll", require_auth=True)

# 文件上传
rate_limit_upload = _make_rate_limit_dep("upload", require_auth=True)

# 健康检查（高额度，不需要认证）
rate_limit_health = _make_rate_limit_dep("health", require_auth=False)
