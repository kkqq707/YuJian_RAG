"""JWT Token 实现

Access Token Payload:
  sub: 用户 ID
  username: 用户名
  role: 角色
  type: "access"
  jti: JWT ID
  iat: 签发时间
  exp: 过期时间
  iss: 签发者
  aud: 受众

Refresh Token Payload:
  sub: 用户 ID
  type: "refresh"
  jti: JWT ID
  iat: 签发时间
  exp: 过期时间
  iss: 签发者
  aud: 受众

安全要求:
- 校验签名
- 校验 exp
- 校验 iss
- 校验 aud
- 校验 type
- Access Token 不能作为 Refresh Token 使用
- Refresh Token 不能访问业务接口
- Token 错误统一转换成安全的 401
- 不返回 Token 内容
- Token 不含 password_hash / API Key
"""

from __future__ import annotations

import hashlib
import uuid
from datetime import datetime, timedelta, timezone

import jwt
from jwt.exceptions import (
    ExpiredSignatureError,
    InvalidAudienceError,
    InvalidIssuerError,
    InvalidSignatureError,
    InvalidTokenError,
)

from backend.app.config import get_settings


# ---------------------------------------------------------------------------
# 动态 JWT Secret — 数据库优先，环境变量兜底
# ---------------------------------------------------------------------------


def _get_jwt_secret() -> str:
    """获取 JWT Secret（数据库优先，.env 兜底）。

    Phase 6D: JWT Secret 从数据库 system_configs 表加载，
    如果数据库尚未初始化则回退到 .env 环境变量。
    """
    try:
        from backend.app.services.llm_config_service import get_jwt_secret_sync
        secret = get_jwt_secret_sync()
        if secret:
            return secret
    except Exception:
        pass

    # 回退到环境变量
    settings = get_settings()
    return settings.JWT_SECRET_KEY


# ---------------------------------------------------------------------------
# 内部辅助
# ---------------------------------------------------------------------------

def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _generate_jti() -> str:
    return str(uuid.uuid4())


# ---------------------------------------------------------------------------
# Token 创建
# ---------------------------------------------------------------------------


def create_access_token(user) -> str:
    """为给定用户创建 Access Token。

    Parameters
    ----------
    user : User
        用户 ORM 实例，需包含 id, username, role 属性

    Returns
    -------
    str
        编码后的 JWT Access Token
    """
    settings = get_settings()
    now = _now_utc()
    payload = {
        "sub": str(user.id),
        "username": user.username,
        "role": user.role,
        "type": "access",
        "jti": _generate_jti(),
        "iat": now,
        "exp": now + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES),
        "iss": settings.JWT_ISSUER,
        "aud": settings.JWT_AUDIENCE,
    }
    return jwt.encode(payload, _get_jwt_secret(), algorithm=settings.JWT_ALGORITHM)


def create_refresh_token(user) -> str:
    """为给定用户创建 Refresh Token。

    Parameters
    ----------
    user : User
        用户 ORM 实例，需包含 id 属性

    Returns
    -------
    str
        编码后的 JWT Refresh Token
    """
    settings = get_settings()
    now = _now_utc()
    jti = _generate_jti()
    payload = {
        "sub": str(user.id),
        "type": "refresh",
        "jti": jti,
        "iat": now,
        "exp": now + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS),
        "iss": settings.JWT_ISSUER,
        "aud": settings.JWT_AUDIENCE,
    }
    return jwt.encode(payload, _get_jwt_secret(), algorithm=settings.JWT_ALGORITHM)


# ---------------------------------------------------------------------------
# Token 解码与校验
# ---------------------------------------------------------------------------


def decode_token(token: str) -> dict:
    """解码 Token，不区分类型。

    Returns
    -------
    dict
        解码后的 payload

    Raises
    ------
    InvalidTokenError
        Token 无效（签名错误、过期、issuer/audience 不匹配等）
    """
    settings = get_settings()
    try:
        payload = jwt.decode(
            token,
            _get_jwt_secret(),
            algorithms=[settings.JWT_ALGORITHM],
            issuer=settings.JWT_ISSUER,
            audience=settings.JWT_AUDIENCE,
            options={"require": ["exp", "iss", "aud", "sub", "type", "jti"]},
        )
        return payload
    except ExpiredSignatureError:
        raise
    except InvalidSignatureError:
        raise
    except InvalidIssuerError:
        raise
    except InvalidAudienceError:
        raise
    except InvalidTokenError:
        raise


def verify_access_token(token: str) -> dict:
    """校验 Access Token。

    Returns
    -------
    dict
        Access Token 的 payload

    Raises
    ------
    InvalidTokenError
        Token 无效或类型不是 access
    """
    payload = decode_token(token)

    if payload.get("type") != "access":
        raise InvalidTokenError("Token 类型错误：需要 access token")

    return payload


def verify_refresh_token(token: str) -> dict:
    """校验 Refresh Token。

    Returns
    -------
    dict
        Refresh Token 的 payload

    Raises
    ------
    InvalidTokenError
        Token 无效或类型不是 refresh
    """
    payload = decode_token(token)

    if payload.get("type") != "refresh":
        raise InvalidTokenError("Token 类型错误：需要 refresh token")

    return payload


# ---------------------------------------------------------------------------
# Token 哈希（用于存储 Refresh Token）
# ---------------------------------------------------------------------------


def hash_token(token: str) -> str:
    """对 Token 进行 SHA-256 哈希（用于数据库存储）。

    数据库中不保存完整 Refresh Token 明文。
    """
    return hashlib.sha256(token.encode("utf-8")).hexdigest()
