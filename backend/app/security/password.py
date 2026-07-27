"""密码安全模块

- 使用 bcrypt 直接进行密码哈希（避免 passlib 与新版本 bcrypt 的兼容性问题）
- 自动生成盐，相同密码两次哈希结果不同
- 验证使用常量时间比较
- 密码强度校验
- 不记录明文密码
- bcrypt 72 字节限制安全处理
"""

from __future__ import annotations

import logging
import re

import bcrypt

logger = logging.getLogger(__name__)

# bcrypt 算法密码最大字节数限制
_BCRYPT_MAX_PASSWORD_BYTES = 72

# bcrypt rounds（适当平衡安全性与性能）
_BCRYPT_ROUNDS = 12


# ---------------------------------------------------------------------------
# 密码标准化 — 所有密码必须经过此函数
# ---------------------------------------------------------------------------


def normalize_password(password: str) -> bytes:
    """统一密码标准化：UTF-8 编码后截断到 72 bytes 以内。

    bcrypt 算法最多处理 72 字节的密码。
    此函数确保所有进入 bcrypt 的密码都经过标准化处理：
    1. UTF-8 编码
    2. 截断到 72 bytes 以内

    所有 hash_password() 和 verify_password() 调用必须经过此函数。

    Returns
    -------
    bytes
        标准化后的密码字节（不超过 72 字节）
    """
    password_str = str(password)
    password_bytes = password_str.encode("utf-8")

    if len(password_bytes) > _BCRYPT_MAX_PASSWORD_BYTES:
        password_bytes = password_bytes[:_BCRYPT_MAX_PASSWORD_BYTES]
        logger.debug(
            "密码从原始长度截断为 %d 字节以符合 bcrypt 限制",
            _BCRYPT_MAX_PASSWORD_BYTES,
        )

    return password_bytes


# ---------------------------------------------------------------------------
# 常见弱密码列表（最小集合）
# ---------------------------------------------------------------------------
_COMMON_PASSWORDS: set[str] = {
    "password", "1234567890", "123456789", "12345678",
    "qwertyuiop", "admin12345", "password123",
    "abc1234567", "1111111111", "0000000000",
}


# ---------------------------------------------------------------------------
# 公开 API
# ---------------------------------------------------------------------------


def hash_password(password: str) -> str:
    """对密码进行安全哈希。

    使用 bcrypt 算法，自动生成随机盐。
    相同密码两次调用产生不同结果。

    安全处理:
    - 输入强制转换为字符串
    - 通过 normalize_password() 统一标准化（UTF-8 编码 + 72 字节截断）
    - 直接使用 bcrypt 库，避免 passlib 兼容性问题

    Returns
    -------
    str
        bcrypt 哈希字符串
    """
    safe_bytes = normalize_password(password)
    hashed = bcrypt.hashpw(safe_bytes, bcrypt.gensalt(rounds=_BCRYPT_ROUNDS))
    return hashed.decode("utf-8")


def verify_password(plain_password: str, password_hash: str) -> bool:
    """验证密码是否匹配。

    使用常量时间比较，防止时序攻击。

    安全处理:
    - 通过 normalize_password() 统一标准化
    - 任何异常均返回 False，不向调用方暴露内部错误
    - 包括 bcrypt 版本兼容性问题、格式错误等
    """
    try:
        safe_bytes = normalize_password(plain_password)
        hash_bytes = password_hash.encode("utf-8")
        return bcrypt.checkpw(safe_bytes, hash_bytes)
    except ValueError:
        # bcrypt 相关错误（格式问题等）
        return False
    except Exception:
        # 任何其他意外异常也安全处理
        logger.warning("密码验证过程中发生意外异常", exc_info=True)
        return False


def validate_password_strength(password: str, username: str | None = None) -> tuple[bool, str | None]:
    """验证密码强度。

    规则:
    - 最少 10 个字符
    - 至少包含字母
    - 至少包含数字
    - 不允许纯数字
    - 不允许与用户名相同
    - 不允许常见弱密码

    Returns
    -------
    (valid, error_message)
        valid=True 表示密码通过校验
        valid=False 时 error_message 包含失败原因
    """
    if not password or len(password) < 10:
        return False, "密码长度至少 10 个字符"

    if re.match(r'^\d+$', password):
        return False, "密码不能为纯数字"

    if not re.search(r'[a-zA-Z]', password):
        return False, "密码必须包含至少一个字母"

    if not re.search(r'\d', password):
        return False, "密码必须包含至少一个数字"

    if username and password.lower() == username.lower():
        return False, "密码不能与用户名相同"

    if password.lower() in _COMMON_PASSWORDS:
        return False, "密码过于常见，请选择更安全的密码"

    return True, None
