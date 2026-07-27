"""配置加密服务 — 使用 Fernet (AES-128-CBC + HMAC-SHA256) 加密敏感配置

提供:
- encrypt(): 加密明文 → 返回 base64 密文
- decrypt(): 解密密文 → 返回明文
- get_encryption_key(): 获取或自动生成加密主密钥

安全策略:
- 加密主密钥存储在 .env 的 CONFIG_ENCRYPTION_KEY
- 首次启动自动生成并写入 .env
- 密文不包含原始 Key 前缀（如 sk-）
- 解密失败时抛出明确错误
"""

from __future__ import annotations

import logging
import os
import secrets
from pathlib import Path

from cryptography.fernet import Fernet, InvalidToken

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# 项目根目录
# ---------------------------------------------------------------------------
_PROJECT_ROOT: Path = Path(__file__).resolve().parent.parent.parent.parent
_ENV_FILE: Path = _PROJECT_ROOT / ".env"
_ENV_KEY_NAME: str = "CONFIG_ENCRYPTION_KEY"


# ---------------------------------------------------------------------------
# 密钥管理
# ---------------------------------------------------------------------------


def get_encryption_key() -> bytes:
    """获取或自动生成加密主密钥。

    优先级:
    1. 环境变量 CONFIG_ENCRYPTION_KEY
    2. .env 文件中的 CONFIG_ENCRYPTION_KEY
    3. 自动生成并写入 .env

    Returns
    -------
    bytes
        Fernet 兼容的 32 字节 url-safe base64 编码密钥
    """
    # 1. 先检查环境变量
    key_str = os.getenv(_ENV_KEY_NAME)
    if key_str:
        return _validate_and_encode_key(key_str)

    # 2. 检查 .env 文件
    if _ENV_FILE.exists():
        key_str = _read_key_from_env_file()
        if key_str:
            # 加载到环境变量以便后续使用
            os.environ[_ENV_KEY_NAME] = key_str
            return _validate_and_encode_key(key_str)

    # 3. 自动生成并持久化
    return _generate_and_persist_key()


def _validate_and_encode_key(key_str: str) -> bytes:
    """验证密钥格式并转换为 bytes。"""
    key_str = key_str.strip()
    if not key_str:
        raise ValueError("加密密钥不能为空")

    # 如果已经是 base64 编码的 Fernet key（44 字符，以 = 结尾）
    # 直接使用
    try:
        return key_str.encode("utf-8")
    except Exception:
        pass

    # 否则将原始字符串用作种子生成 Fernet key
    import base64
    import hashlib
    digest = hashlib.sha256(key_str.encode("utf-8")).digest()
    return base64.urlsafe_b64encode(digest)


def _read_key_from_env_file() -> str | None:
    """从 .env 文件中读取 CONFIG_ENCRYPTION_KEY。"""
    try:
        with open(_ENV_FILE, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line.startswith("#") or "=" not in line:
                    continue
                k, _, v = line.partition("=")
                if k.strip() == _ENV_KEY_NAME:
                    val = v.strip().strip('"').strip("'")
                    if val:
                        return val
    except Exception:
        pass
    return None


def _generate_and_persist_key() -> bytes:
    """生成新的 Fernet 密钥并追加到 .env 文件。"""
    key_bytes = Fernet.generate_key()
    key_str = key_bytes.decode("utf-8")

    # 写入 .env
    try:
        _ENV_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(_ENV_FILE, "a", encoding="utf-8") as f:
            f.write(f"\n# 配置加密主密钥（自动生成）\n{_ENV_KEY_NAME}={key_str}\n")
        logger.info("已自动生成 CONFIG_ENCRYPTION_KEY 并写入 .env")
    except Exception as e:
        logger.warning("无法将 CONFIG_ENCRYPTION_KEY 写入 .env: %s", e)

    # 同时加载到环境变量
    os.environ[_ENV_KEY_NAME] = key_str

    return key_bytes


# ---------------------------------------------------------------------------
# 加密 / 解密
# ---------------------------------------------------------------------------


def encrypt(plaintext: str) -> str:
    """加密明文字符串。

    Parameters
    ----------
    plaintext : str
        待加密的明文

    Returns
    -------
    str
        base64 编码的密文字符串

    Raises
    ------
    ValueError
        明文为空时抛出
    """
    if not plaintext:
        raise ValueError("不能加密空字符串")

    key = get_encryption_key()
    f = Fernet(key)
    token = f.encrypt(plaintext.encode("utf-8"))
    return token.decode("utf-8")


def decrypt(ciphertext: str) -> str:
    """解密密文字符串。

    Parameters
    ----------
    ciphertext : str
        base64 编码的密文字符串

    Returns
    -------
    str
        解密后的明文

    Raises
    ------
    ValueError
        密文为空或解密失败时抛出
    """
    if not ciphertext:
        raise ValueError("不能解密空字符串")

    key = get_encryption_key()
    f = Fernet(key)

    try:
        plaintext = f.decrypt(ciphertext.encode("utf-8"))
        return plaintext.decode("utf-8")
    except InvalidToken as e:
        raise ValueError(f"解密失败：密文无效或加密密钥不匹配 ({e})") from e
    except Exception as e:
        raise ValueError(f"解密失败: {e}") from e
