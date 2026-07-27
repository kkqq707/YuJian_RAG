"""LLM 客户端 — OpenAI-compatible 大模型统一接口

提供:
- get_llm(): 创建或获取缓存的 ChatOpenAI 实例
- clear_llm_cache(): 清除 get_llm() 缓存
- test_llm_connection(): 最小连接验证
- sanitize_llm_error(): 将 API 异常转换为安全的中文消息
- list_available_models(): DeepSeek 模型列表诊断（仅在 provider=deepseek 时可用）
- get_active_llm_params(): 获取当前有效的 LLM 参数（数据库优先，环境变量兜底）

配置优先级:
1. 数据库 system_configs / llm_configs 表（Phase 6D）
2. 环境变量 / .env 文件（兼容旧配置）
"""

from __future__ import annotations

import json
import logging
import time
from functools import lru_cache
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError

from langchain_openai import ChatOpenAI

from src.config import (
    API_KEY,
    BASE_URL,
    LLM_MODEL_NAME,
    LLM_PROVIDER,
    TEMPERATURE,
    REQUEST_TIMEOUT,
    MAX_RETRIES,
    _API_KEY_SOURCE,
    validate_llm_config,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# 动态配置桥接 — 数据库优先，环境变量兜底
# ---------------------------------------------------------------------------


def get_active_llm_params() -> dict:
    """获取当前有效的 LLM 调用参数。

    优先级: 数据库配置 > 环境变量。
    如果数据库中有启用的 LLM 配置，使用数据库配置；
    否则回退到 src/config 的环境变量配置。

    Returns
    -------
    dict
        {"api_key": str, "base_url": str, "model": str, "provider": str,
         "source": "database" | "env"}
    """
    try:
        from backend.app.services.llm_config_service import get_active_llm_config
        db_config = get_active_llm_config()
        if db_config and db_config.api_key:
            logger.info(
                "使用数据库 LLM 配置: provider=%s, model=%s, base_url=%s",
                db_config.provider, db_config.model, db_config.base_url,
            )
            return {
                "api_key": db_config.api_key,
                "base_url": db_config.base_url or "",
                "model": db_config.model or LLM_MODEL_NAME,
                "provider": db_config.provider or LLM_PROVIDER,
                "source": "database",
            }
        else:
            if db_config:
                logger.warning(
                    "数据库 LLM 配置存在但 api_key 为空 (id=%s, provider=%s, model=%s)，回退到环境变量",
                    db_config.id, db_config.provider, db_config.model,
                )
            else:
                logger.info("数据库中没有启用的 LLM 配置，回退到环境变量")
    except Exception as e:
        logger.warning("无法读取数据库 LLM 配置 (%s)，回退到环境变量", e)

    # 回退到环境变量
    logger.info("使用环境变量 LLM 配置: provider=%s, model=%s", LLM_PROVIDER, LLM_MODEL_NAME)
    return {
        "api_key": API_KEY,
        "base_url": BASE_URL or "",
        "model": LLM_MODEL_NAME,
        "provider": LLM_PROVIDER,
        "source": "env",
    }


# ---------------------------------------------------------------------------
# 缓存清理
# ---------------------------------------------------------------------------


def clear_llm_cache() -> None:
    """清除 get_llm() 的 LRU 缓存。

    在配置变更（如切换 API Key、模型名、Base URL）后必须调用，
    以确保下次 get_llm() 使用最新配置创建客户端。
    """
    get_llm.cache_clear()
    logger.debug("get_llm() 缓存已清除")


# ---------------------------------------------------------------------------
# 公开函数
# ---------------------------------------------------------------------------


@lru_cache(maxsize=1)
def get_llm() -> ChatOpenAI:
    """获取缓存的 ChatOpenAI 实例。

    优先使用数据库配置（Phase 6D），数据库无配置时回退到环境变量。
    配置无效时抛出 ValueError，不在 import 时发起 API 请求。

    Returns
    -------
    ChatOpenAI

    Raises
    ------
    ValueError
        配置不完整时抛出中文错误消息
    """
    params = get_active_llm_params()

    if not params["api_key"]:
        raise ValueError(
            "LLM 配置不完整，无法创建客户端：\n"
            "  - API Key 未设置（请在管理后台配置或设置环境变量）"
        )
    if not params["model"]:
        raise ValueError(
            "LLM 配置不完整，无法创建客户端：\n"
            "  - 模型名称未设置（请在管理后台配置或设置环境变量）"
        )

    kwargs: dict = {
        "model": params["model"],
        "api_key": params["api_key"],
        "temperature": TEMPERATURE,
        "timeout": REQUEST_TIMEOUT,
        "max_retries": MAX_RETRIES,
    }
    if params["base_url"]:
        kwargs["base_url"] = params["base_url"]

    logger.debug(
        "创建 ChatOpenAI 实例 (model=%s, provider=%s, source=%s)",
        params["model"], params["provider"], params["source"],
    )
    return ChatOpenAI(**kwargs)


def test_llm_connection() -> dict:
    """发送最小请求验证 LLM 连接。

    只要求模型回复 "OK"，不携带任何知识库正文。
    执行前会先清理 get_llm() 缓存，确保使用最新配置。
    优先使用数据库配置，数据库无配置时回退到环境变量。

    Returns
    -------
    dict
        {"success": bool, "model": str, "latency_seconds": float,
         "response_preview": str, "error": str | None,
         "source": "database" | "env"}
    """
    # 每次连接测试前清理缓存，避免使用过期的旧客户端
    clear_llm_cache()

    params = get_active_llm_params()

    result = {
        "success": False,
        "model": params["model"] or "<not set>",
        "latency_seconds": 0.0,
        "response_preview": "",
        "error": None,
        "source": params["source"],
    }

    t0 = 0.0

    # 1. 检查配置
    if not params["api_key"]:
        result["error"] = "配置不完整：API Key 未设置"
        return result
    if not params["model"]:
        result["error"] = "配置不完整：模型名称未设置"
        return result

    # 2. 发送最小请求
    try:
        llm = get_llm()
        test_message = "请只回复 OK。不要输出其他任何内容。"

        t0 = time.perf_counter()
        response = llm.invoke(test_message)
        elapsed = time.perf_counter() - t0

        result["latency_seconds"] = round(elapsed, 3)
        content = response.content if hasattr(response, "content") else str(response)
        preview = content.strip()[:50]
        result["response_preview"] = preview
        result["success"] = True

    except Exception as exc:
        result["error"] = sanitize_llm_error(
            exc,
            provider=params.get("provider", ""),
            model=params.get("model", ""),
        )
        if t0 > 0:
            result["latency_seconds"] = round(time.perf_counter() - t0, 3)
        result["response_preview"] = ""

    return result


def sanitize_llm_error(error: Exception, provider: str = "", model: str = "") -> str:
    """将 LLM 相关异常转换为安全、简短、可读的中文消息。

    不会在返回的消息中包含 API Key、Token 或完整请求头。

    Parameters
    ----------
    error : Exception
        get_llm() 或 LLM 调用过程中抛出的原始异常
    provider : str
        当前使用的 provider（用于生成针对性错误消息），为空时从 get_active_llm_params 获取
    model : str
        当前使用的模型名（用于生成针对性错误消息），为空时从 get_active_llm_params 获取

    Returns
    -------
    str
    """
    # 尝试获取实际使用的配置（用于生成准确的错误消息）
    _provider = provider
    _model = model
    if not _provider or not _model:
        try:
            params = get_active_llm_params()
            if not _provider:
                _provider = params.get("provider", LLM_PROVIDER)
            if not _model:
                _model = params.get("model", LLM_MODEL_NAME)
        except Exception:
            _provider = _provider or LLM_PROVIDER
            _model = _model or LLM_MODEL_NAME

    _is_deepseek = (_provider == "deepseek" or "deepseek" in str(_provider).lower())

    msg = str(error).lower()
    msg_original = str(error)

    # ── 401: 认证失败 ──
    if "401" in msg_original or "unauthorized" in msg:
        if _is_deepseek:
            return (
                "DeepSeek API Key 无效或已失效。"
                "请在管理后台 AI 服务配置中检查 API Key 是否正确。"
            )
        if "invalid" in msg or "incorrect" in msg:
            return "API Key 无效，请在管理后台检查 API Key 是否正确"
        return "认证失败 (401)：API Key 无效或已过期"

    # ── 402 / 余额不足 ──
    if "402" in msg_original or "payment_required" in msg:
        if _is_deepseek:
            return "DeepSeek 账户余额不足或计费状态异常。请登录 DeepSeek 开放平台检查账户余额。"
        return "账户余额不足或计费状态异常 (402)"

    # ── 403: 无权限 ──
    if "403" in msg_original or "forbidden" in msg:
        return "无权限访问该模型 (403)，请检查 API Key 是否有访问权限"

    # ── 404: 模型或地址错误 ──
    if "404" in msg_original or "not found" in msg:
        if _is_deepseek:
            return (
                f"DeepSeek 模型名称或 Base URL 配置错误 (404)。"
                f"当前模型名: '{_model}'，请确认该模型在 DeepSeek 开放平台可用。"
            )
        if "model" in msg:
            return f"模型不存在 (404)：'{_model}' 可能名称错误"
        return "请求地址不存在 (404)，请检查 Base URL 和模型名称是否正确"

    # ── 429: 频率限制 ──
    if "429" in msg_original:
        if _is_deepseek:
            return "DeepSeek 请求频率受限，请稍后重试。"
        if "quota" in msg or "insufficient" in msg:
            return "API 额度不足 (429)，请检查账户余额或配额"
        return "请求频率过高 (429)，请稍后重试"

    # ── Timeout ──
    if "timeout" in msg or "timed out" in msg or ("connection" in msg and "time" in msg):
        return "请求超时：模型响应时间过长，请稍后重试或检查网络连接"

    # ── Connection error ──
    if "connection" in msg or "connect" in msg or "network" in msg:
        return "网络连接失败：无法连接到 API 服务器，请检查网络或 Base URL"

    # ── SSL error ──
    if "ssl" in msg or "certificate" in msg or "tls" in msg:
        return "SSL 证书验证失败，请检查 Base URL 和网络代理设置"

    # ── Model not found variations ──
    if "model" in msg and ("not found" in msg or "not_found" in msg or "doesn't exist" in msg):
        return f"模型 '{_model}' 不存在，请检查模型名称是否正确"

    # ── Generic fallback — 不包含原始错误内容，避免泄露请求头/API Key ──
    logger.warning("LLM 调用异常 (已脱敏): %s", _safe_error_summary(error))
    return "调用大模型时发生未知错误，请稍后重试"


def list_available_models() -> dict:
    """调用 DeepSeek 官方模型列表接口获取当前账号可用模型。

    优先使用数据库配置，数据库无配置时使用环境变量。
    使用 Bearer 认证，不打印请求头，不返回 API Key。
    仅在 provider=deepseek 时可用。

    Returns
    -------
    dict
        {"success": bool, "models": list[str], "error": str | None,
         "current_model_available": bool}
    """
    result: dict = {
        "success": False,
        "models": [],
        "error": None,
        "current_model_available": False,
    }

    # 优先使用数据库配置，回退到环境变量
    params = get_active_llm_params()
    _provider = params.get("provider", LLM_PROVIDER)
    _api_key = params.get("api_key", API_KEY)
    _model = params.get("model", LLM_MODEL_NAME)

    if _provider != "deepseek":
        result["error"] = f"list_available_models() 仅在 provider=deepseek 时可用，当前 provider={_provider}"
        return result

    if not _api_key:
        result["error"] = "API Key 未配置，无法请求模型列表"
        return result

    url = "https://api.deepseek.com/models"
    req = Request(url)
    req.add_header("Authorization", f"Bearer {_api_key}")
    req.add_header("Accept", "application/json")

    try:
        with urlopen(req, timeout=30) as resp:
            body = resp.read().decode("utf-8")
            data = json.loads(body)

        # DeepSeek 模型列表接口返回格式: {"object": "list", "data": [{"id": "...", ...}, ...]}
        if isinstance(data, dict) and "data" in data:
            models_data = data["data"]
        elif isinstance(data, list):
            models_data = data
        else:
            result["error"] = f"模型列表接口返回格式异常: {type(data).__name__}"
            return result

        model_ids = []
        for item in models_data:
            if isinstance(item, dict) and "id" in item:
                model_ids.append(item["id"])
            elif isinstance(item, str):
                model_ids.append(item)

        result["models"] = model_ids
        result["success"] = True
        result["current_model_available"] = _model in model_ids

    except HTTPError as e:
        result["error"] = sanitize_llm_error(e)
        logger.warning("模型列表请求失败 (HTTP %d)", e.code)
    except URLError as e:
        result["error"] = f"网络连接失败：无法访问 DeepSeek 模型列表接口 ({_safe_error_summary(e)})"
    except json.JSONDecodeError:
        result["error"] = "模型列表接口返回数据格式解析失败"
    except Exception as e:
        result["error"] = sanitize_llm_error(e)

    return result


# ---------------------------------------------------------------------------
# 内部辅助
# ---------------------------------------------------------------------------


def _safe_error_summary(error: Exception) -> str:
    """提取异常类型和简短摘要，不包含敏感信息。"""
    error_type = type(error).__name__
    # 只取第一行，避免完整堆栈
    first_line = str(error).split("\n")[0]
    # 截断过长的消息
    if len(first_line) > 200:
        first_line = first_line[:200] + "..."
    return f"{error_type}: {first_line}"
