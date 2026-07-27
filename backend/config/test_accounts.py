"""测试账号配置

仅用于测试/开发环境。
生产环境禁止加载此模块。

安全:
- 密码仅用于测试环境，不用于生产
- 此文件不应包含生产环境的任何密钥
"""

from __future__ import annotations

import os

# ---------------------------------------------------------------------------
# 固定测试账号
# ---------------------------------------------------------------------------

# 管理员
ADMIN_USERNAME: str = "admin"
ADMIN_PASSWORD: str = "admin123456"

# 普通用户
USER_USERNAME: str = "test"
USER_PASSWORD: str = "test123456"


def is_production() -> bool:
    """检查当前是否为生产环境。

    生产环境特征:
    - APP_ENV 设置为 "production"
    - 或 PYTHONPRODUCTION 环境变量存在
    """
    return os.environ.get("APP_ENV", "").lower() == "production"


def guard_production() -> None:
    """生产环境保护 — 如果在生产环境加载此模块则报错。"""
    if is_production():
        raise RuntimeError(
            "backend.config.test_accounts 不应在生产环境中加载。"
            "当前 APP_ENV=production，已阻止加载。"
        )
