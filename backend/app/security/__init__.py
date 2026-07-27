"""安全模块

提供:
- 密码哈希与校验 (password.py)
- JWT Token 签发与校验 (jwt.py)
- 认证依赖注入 (dependencies.py)
"""

from backend.app.security.password import (
    hash_password,
    validate_password_strength,
    verify_password,
)
from backend.app.security.jwt import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_token,
    verify_access_token,
    verify_refresh_token,
)

__all__ = [
    # password
    "hash_password",
    "verify_password",
    "validate_password_strength",
    # jwt
    "create_access_token",
    "create_refresh_token",
    "decode_token",
    "hash_token",
    "verify_access_token",
    "verify_refresh_token",
]
