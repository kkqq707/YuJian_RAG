"""LLM 配置服务 — 动态读取/写入 LLM 配置，含缓存机制

提供:
- get_active_llm_config(): 获取当前启用的 LLM 配置（从缓存）
- save_llm_config(): 保存/更新 LLM 配置并刷新缓存
- test_llm_connection(): 使用给定配置测试连接
- get_models(): 获取可用模型列表
- refresh_cache(): 强制刷新配置缓存
- get_jwt_secret(): 获取或自动初始化 JWT Secret

缓存策略:
- 内存缓存，管理员保存配置时立即刷新
- 普通请求读取缓存，避免每次查询数据库
"""

from __future__ import annotations

import logging
import secrets
import threading
import time
from dataclasses import dataclass, field
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.database import SessionLocal
from backend.app.models.llm_config import LLMConfig
from backend.app.models.system_config import SystemConfig
from backend.app.services.encryption_service import encrypt, decrypt

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# 数据类
# ---------------------------------------------------------------------------


@dataclass
class LLMConfigData:
    """LLM 配置数据传输对象 — 不含加密的 API Key。"""

    id: Optional[int] = None
    provider: str = "openai-compatible"
    base_url: str = ""
    api_key: str = ""  # 明文（仅内存中使用，不入库）
    model: str = ""
    enabled: bool = True


# ---------------------------------------------------------------------------
# 缓存
# ---------------------------------------------------------------------------


class LLMConfigCache:
    """线程安全的 LLM 配置缓存。"""

    def __init__(self):
        self._lock = threading.Lock()
        self._config: Optional[LLMConfigData] = None
        self._last_refresh: float = 0.0
        self._jwt_secret: Optional[str] = None

    def get_config(self) -> Optional[LLMConfigData]:
        """获取缓存的 LLM 配置。"""
        with self._lock:
            return self._config

    def set_config(self, config: Optional[LLMConfigData]) -> None:
        """更新缓存的 LLM 配置。"""
        with self._lock:
            self._config = config
            self._last_refresh = time.time()

    def get_jwt_secret(self) -> Optional[str]:
        """获取缓存的 JWT Secret。"""
        with self._lock:
            return self._jwt_secret

    def set_jwt_secret(self, secret: str) -> None:
        """更新缓存的 JWT Secret。"""
        with self._lock:
            self._jwt_secret = secret

    @property
    def last_refresh(self) -> float:
        with self._lock:
            return self._last_refresh


# 全局单例缓存
_cache = LLMConfigCache()


# ---------------------------------------------------------------------------
# 公开 API
# ---------------------------------------------------------------------------


def get_active_llm_config() -> Optional[LLMConfigData]:
    """获取当前启用的 LLM 配置。

    优先从缓存读取，缓存未命中时从数据库加载。

    Returns
    -------
    LLMConfigData or None
        启用的 LLM 配置，未配置时返回 None
    """
    cached = _cache.get_config()
    if cached is not None:
        return cached

    return _load_config_from_db()


def get_current_llm_config() -> dict:
    """统一获取当前 LLM 配置（供系统监控、系统设置、LLM 调用等模块使用）。

    仅从数据库读取，不回退到环境变量。
    环境变量仅用于 LLM 调用时的兜底（见 src/llm_client.get_active_llm_params）。

    Returns
    -------
    dict
        {
            "provider": str | None,     # 提供商名称，如 "deepseek"
            "model": str | None,        # 模型名称，如 "deepseek-v4-flash"
            "base_url": str | None,     # API Base URL
            "enabled": bool,            # 是否启用
            "configured": bool,         # 是否已配置（有 api_key）
            "source": "database" | None,# 配置来源
        }
    """
    try:
        config = get_active_llm_config()
    except Exception as e:
        logger.warning("读取 LLM 配置失败: %s", e)
        config = None

    if config is None:
        return {
            "provider": None,
            "model": None,
            "base_url": None,
            "enabled": False,
            "configured": False,
            "source": None,
        }

    return {
        "provider": config.provider or None,
        "model": config.model or None,
        "base_url": config.base_url or None,
        "enabled": config.enabled,
        "configured": bool(config.api_key),
        "source": "database",
    }


def save_llm_config(data: LLMConfigData) -> LLMConfigData:
    """保存或更新 LLM 配置。

    - 如果 data.id 为 None 则创建新配置
    - 如果启用了此配置，自动禁用其他配置（同一时间只有一个启用）
    - 保存后自动刷新缓存

    Parameters
    ----------
    data : LLMConfigData
        配置数据（api_key 为明文）

    Returns
    -------
    LLMConfigData
        保存后的配置（api_key 已置空）
    """
    db: Session = SessionLocal()
    try:
        if data.id is not None:
            # 更新现有配置
            stmt = select(LLMConfig).where(LLMConfig.id == data.id)
            config = db.execute(stmt).scalar_one_or_none()
            if config is None:
                raise ValueError(f"LLM 配置不存在: id={data.id}")
        else:
            # 创建新配置
            config = LLMConfig()
            db.add(config)

        # 更新字段
        config.provider = data.provider or "openai-compatible"
        config.base_url = data.base_url or ""
        config.model = data.model or ""

        # 仅当提供了新的 API Key 时才更新
        if data.api_key:
            config.api_key_encrypted = encrypt(data.api_key)

        # 处理启用状态
        if data.enabled:
            # 禁用所有其他配置
            _disable_other_configs(db, exclude_id=config.id)
        config.enabled = data.enabled

        db.flush()
        db.refresh(config)
        db.commit()

        # 构建返回数据
        result = LLMConfigData(
            id=config.id,
            provider=config.provider,
            base_url=config.base_url,
            api_key="",  # 不返回明文 API Key
            model=config.model,
            enabled=config.enabled,
        )

        # 刷新 LLM 配置缓存
        refresh_cache()

        # 同时清除 LangChain LLM 实例缓存，确保下次请求使用新配置
        _clear_langchain_llm_cache()

        logger.info("LLM 配置已保存: provider=%s, model=%s, enabled=%s",
                     config.provider, config.model, config.enabled)
        return result

    finally:
        db.close()


def get_llm_config_for_display(db: Session) -> dict:
    """获取 LLM 配置用于管理后台展示（API Key 脱敏）。

    Parameters
    ----------
    db : Session
        数据库会话

    Returns
    -------
    dict
        包含脱敏后 API Key 的配置信息
    """
    stmt = select(LLMConfig).where(LLMConfig.enabled == True).limit(1)
    config = db.execute(stmt).scalar_one_or_none()

    if config is None:
        return {
            "configured": False,
            "provider": None,
            "base_url": None,
            "model": None,
            "enabled": False,
            "api_key_masked": None,
        }

    # 解密 API Key 用于脱敏
    api_key_masked = ""
    if config.api_key_encrypted:
        try:
            plain = decrypt(config.api_key_encrypted)
            api_key_masked = _mask_api_key(plain)
        except Exception:
            api_key_masked = "********"

    return {
        "configured": True,
        "id": config.id,
        "provider": config.provider,
        "base_url": config.base_url,
        "model": config.model,
        "enabled": config.enabled,
        "api_key_masked": api_key_masked,
    }


def test_llm_connection_with_config(
    base_url: str,
    api_key: str,
    model: str,
) -> dict:
    """使用给定配置测试 LLM 连接。

    发送最小测试消息 "hello"，验证连接可用性。

    Parameters
    ----------
    base_url : str
        API Base URL
    api_key : str
        API Key（明文）
    model : str
        模型名称

    Returns
    -------
    dict
        {"success": bool, "model": str, "latency_ms": int, "error": str | None}
    """
    import sys
    from pathlib import Path

    # 确保项目根在 sys.path 中
    project_root = Path(__file__).resolve().parent.parent.parent.parent
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))

    from langchain_openai import ChatOpenAI

    t0 = time.perf_counter()

    try:
        kwargs = {
            "model": model,
            "api_key": api_key,
            "temperature": 0.1,
            "timeout": 30,
            "max_retries": 1,
        }
        if base_url:
            kwargs["base_url"] = base_url

        llm = ChatOpenAI(**kwargs)
        response = llm.invoke("hello")
        elapsed_ms = round((time.perf_counter() - t0) * 1000)

        content = response.content if hasattr(response, "content") else str(response)

        return {
            "success": True,
            "model": model,
            "latency_ms": elapsed_ms,
            "response_preview": content.strip()[:50] if content else "",
            "error": None,
        }

    except Exception as e:
        elapsed_ms = round((time.perf_counter() - t0) * 1000) if t0 > 0 else 0
        from src.llm_client import sanitize_llm_error
        return {
            "success": False,
            "model": model,
            "latency_ms": elapsed_ms,
            "response_preview": "",
            "error": sanitize_llm_error(e),
        }


def get_available_models() -> list[dict]:
    """获取可用模型列表。

    返回常用 OpenAI-compatible 模型列表。
    如果启用了 DeepSeek，尝试从 API 获取真实模型列表。

    Returns
    -------
    list[dict]
        [{"name": "deepseek-chat", "provider": "DeepSeek"}, ...]
    """
    import sys
    from pathlib import Path

    project_root = Path(__file__).resolve().parent.parent.parent.parent
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))

    # 默认模型列表
    default_models = [
        {"name": "deepseek-chat", "provider": "DeepSeek"},
        {"name": "deepseek-reasoner", "provider": "DeepSeek"},
        {"name": "deepseek-v3", "provider": "DeepSeek"},
        {"name": "deepseek-v4-flash", "provider": "DeepSeek"},
        {"name": "deepseek-v4-pro", "provider": "DeepSeek"},
        {"name": "gpt-4.1", "provider": "OpenAI"},
        {"name": "gpt-4.1-mini", "provider": "OpenAI"},
        {"name": "gpt-4o", "provider": "OpenAI"},
        {"name": "gpt-4o-mini", "provider": "OpenAI"},
        {"name": "claude-3-opus", "provider": "Anthropic"},
        {"name": "claude-3-sonnet", "provider": "Anthropic"},
        {"name": "qwen-turbo", "provider": "Alibaba Cloud"},
        {"name": "qwen-plus", "provider": "Alibaba Cloud"},
    ]

    # 尝试从启用的 LLM 配置中动态获取模型
    try:
        config = get_active_llm_config()
        if config and config.api_key and "deepseek" in (config.base_url or "").lower():
            from src.llm_client import list_available_models
            result = list_available_models()
            if result.get("success") and result.get("models"):
                dynamic_models = []
                for m in result["models"]:
                    dynamic_models.append({
                        "name": m,
                        "provider": "DeepSeek (动态)",
                    })
                # 合并去重
                existing_names = {m["name"] for m in default_models}
                for m in dynamic_models:
                    if m["name"] not in existing_names:
                        default_models.append(m)
    except Exception:
        pass

    return default_models


def refresh_cache() -> None:
    """强制刷新 LLM 配置缓存（管理员保存配置后调用）。"""
    _cache.set_config(None)  # 清除缓存，下次请求时重新加载
    _load_config_from_db()
    logger.info("LLM 配置缓存已刷新")


# ---------------------------------------------------------------------------
# JWT Secret 管理
# ---------------------------------------------------------------------------


def get_jwt_secret(db: Session) -> str:
    """获取或自动初始化 JWT Secret。

    流程:
    1. 检查内存缓存
    2. 检查数据库 system_configs 表
    3. 检查 .env 环境变量
    4. 自动生成并加密保存到数据库

    Parameters
    ----------
    db : Session
        数据库会话

    Returns
    -------
    str
        JWT Secret 明文
    """
    # 1. 内存缓存
    cached = _cache.get_jwt_secret()
    if cached:
        return cached

    # 2. 数据库
    stmt = select(SystemConfig).where(SystemConfig.config_key == "jwt_secret_key")
    config = db.execute(stmt).scalar_one_or_none()

    if config and config.config_value_encrypted:
        try:
            secret = decrypt(config.config_value_encrypted)
            _cache.set_jwt_secret(secret)
            logger.info("JWT Secret 已从数据库加载")
            return secret
        except Exception as e:
            logger.warning("JWT Secret 解密失败，将重新生成: %s", e)

    # 3. 检查 .env 兼容（迁移期间）
    import os
    env_secret = os.getenv("JWT_SECRET_KEY")
    if env_secret and not (config and config.config_value_encrypted):
        # 将 .env 中的值迁移到数据库
        logger.info("检测到 .env 中的 JWT_SECRET_KEY，正在迁移到数据库...")
        _save_jwt_secret_to_db(db, env_secret)
        _cache.set_jwt_secret(env_secret)
        return env_secret

    # 4. 自动生成
    logger.info("JWT Secret 未配置，正在自动生成...")
    new_secret = secrets.token_urlsafe(48)
    _save_jwt_secret_to_db(db, new_secret)
    _cache.set_jwt_secret(new_secret)
    logger.info("JWT Secret 已自动生成并保存到数据库")

    return new_secret


def get_jwt_secret_sync() -> str:
    """同步获取 JWT Secret（供启动时使用，不依赖 FastAPI Depends）。"""
    cached = _cache.get_jwt_secret()
    if cached:
        return cached

    db: Session = SessionLocal()
    try:
        return get_jwt_secret(db)
    finally:
        db.close()


def _save_jwt_secret_to_db(db: Session, secret: str) -> None:
    """将 JWT Secret 加密后保存到数据库。"""
    encrypted = encrypt(secret)

    stmt = select(SystemConfig).where(SystemConfig.config_key == "jwt_secret_key")
    config = db.execute(stmt).scalar_one_or_none()

    if config:
        config.config_value_encrypted = encrypted
    else:
        config = SystemConfig(
            config_key="jwt_secret_key",
            config_value_encrypted=encrypted,
            description="JWT Token 签名密钥（自动生成，禁止修改）",
        )
        db.add(config)

    db.flush()
    db.commit()


# ---------------------------------------------------------------------------
# 内部辅助
# ---------------------------------------------------------------------------


def _load_config_from_db() -> Optional[LLMConfigData]:
    """从数据库加载当前启用的 LLM 配置。"""
    db: Session = SessionLocal()
    try:
        stmt = select(LLMConfig).where(LLMConfig.enabled == True).limit(1)
        config = db.execute(stmt).scalar_one_or_none()

        if config is None:
            _cache.set_config(None)
            return None

        # 解密 API Key
        api_key = ""
        if config.api_key_encrypted:
            try:
                api_key = decrypt(config.api_key_encrypted)
            except Exception as e:
                logger.warning("LLM 配置 API Key 解密失败: %s", e)

        data = LLMConfigData(
            id=config.id,
            provider=config.provider,
            base_url=config.base_url or "",
            api_key=api_key,
            model=config.model or "",
            enabled=config.enabled,
        )

        _cache.set_config(data)
        return data

    finally:
        db.close()


def _disable_other_configs(db: Session, exclude_id: Optional[int]) -> None:
    """禁用其他所有启用的 LLM 配置。"""
    from sqlalchemy import update
    stmt = (
        update(LLMConfig)
        .where(LLMConfig.enabled == True)
    )
    if exclude_id is not None:
        stmt = stmt.where(LLMConfig.id != exclude_id)
    stmt = stmt.values(enabled=False)
    db.execute(stmt)


def _mask_api_key(key: str) -> str:
    """将 API Key 脱敏显示。"""
    if not key:
        return "<未设置>"
    if len(key) <= 8:
        return "*" * len(key)
    return key[:4] + "*" * (len(key) - 8) + key[-4:]


def _clear_langchain_llm_cache() -> None:
    """清除 LangChain LLM 实例缓存（get_llm LRU 缓存）。

    在管理员保存 LLM 配置后调用，确保下次问答请求使用最新的模型配置。
    """
    import sys
    from pathlib import Path

    project_root = Path(__file__).resolve().parent.parent.parent.parent
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))

    try:
        from src.llm_client import clear_llm_cache
        clear_llm_cache()
        logger.debug("LangChain LLM 实例缓存已清除")
    except Exception as e:
        logger.warning("清除 LangChain LLM 缓存失败: %s", e)
