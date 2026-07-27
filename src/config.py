"""企业知识库 RAG 问答系统 - 配置文件

使用 python-dotenv 加载项目根目录 .env，统一定义所有路径和参数。
API Key 绝对不会在日志或异常中被打印。

安全策略:
- load_dotenv(override=False) 确保系统环境变量优先于 .env
- 所有 API Key 只通过环境变量注入，不硬编码
- _mask_key() / overview() / validate_llm_config() 均不输出 Key 明文
"""

from __future__ import annotations

import os
from pathlib import Path
from urllib.parse import urlparse

from dotenv import load_dotenv

# ---------------------------------------------------------------------------
# 项目根目录 & .env（系统环境变量优先于 .env）
# ---------------------------------------------------------------------------
PROJECT_ROOT: Path = Path(__file__).resolve().parent.parent

# override=False: 系统环境变量优先，防止 .env 中泄露的 Key 覆盖系统 Key
_load_result = load_dotenv(PROJECT_ROOT / ".env", override=False)

# ---------------------------------------------------------------------------
# 目录
# ---------------------------------------------------------------------------
DATA_DIR: Path = PROJECT_ROOT / "data"  # 保留向后兼容
BUILTIN_DATA_DIR: Path = DATA_DIR / "builtin"
UPLOADS_DATA_DIR: Path = DATA_DIR / "uploads"
STORAGE_DIR: Path = PROJECT_ROOT / "storage"
CHROMA_DIR: Path = STORAGE_DIR / "chroma_db"
METADATA_DB_PATH: Path = STORAGE_DIR / "knowledge_metadata.db"
ASSETS_DIR: Path = PROJECT_ROOT / "assets"

# ---------------------------------------------------------------------------
# 向量库
# ---------------------------------------------------------------------------
COLLECTION_NAME: str = os.getenv("COLLECTION_NAME", "enterprise_knowledge")

# ---------------------------------------------------------------------------
# Embedding
# ---------------------------------------------------------------------------
EMBEDDING_MODEL_NAME: str = os.getenv(
    "EMBEDDING_MODEL_NAME", "BAAI/bge-small-zh-v1.5"
)

# 本地模型路径（优先级最高，设置后不访问网络）
# EMBEDDING_MODEL_PATH 是新配置项，优先使用；EMBEDDING_LOCAL_PATH 保留向后兼容
EMBEDDING_MODEL_PATH: str = os.getenv(
    "EMBEDDING_MODEL_PATH",
    os.getenv("EMBEDDING_LOCAL_PATH", ""),
)

# 向后兼容别名
EMBEDDING_LOCAL_PATH: str = EMBEDDING_MODEL_PATH

# Hugging Face 镜像端点（例如 https://hf-mirror.com）
HF_ENDPOINT: str = os.getenv("HF_ENDPOINT", "")

# 离线模式标志（企业部署默认开启）
HF_HUB_OFFLINE: bool = os.getenv("HF_HUB_OFFLINE", "1") == "1"
TRANSFORMERS_OFFLINE: bool = os.getenv("TRANSFORMERS_OFFLINE", "1") == "1"

# ---- 企业离线部署: 运行时强制设置环境变量 ----
# 确保 huggingface_hub / transformers / datasets 在任何阶段都不会联网
if HF_HUB_OFFLINE:
    os.environ.setdefault("HF_HUB_OFFLINE", "1")
if TRANSFORMERS_OFFLINE:
    os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")
os.environ.setdefault("HF_DATASETS_OFFLINE", "1")

# ---------------------------------------------------------------------------
# 默认值（仅在对应 provider 生效时使用）
# ---------------------------------------------------------------------------
_DEEPSEEK_BASE_URL_DEFAULT = "https://api.deepseek.com"
_DEEPSEEK_MODEL_DEFAULT = "deepseek-chat"

# ---------------------------------------------------------------------------
# API Key — 按优先级: DEEPSEEK > OPENAI > API_KEY > DASHSCOPE
# ---------------------------------------------------------------------------
_API_KEY_SOURCE = ""
API_KEY = ""

for _src, _val in [
    ("DEEPSEEK_API_KEY", os.getenv("DEEPSEEK_API_KEY")),
    ("OPENAI_API_KEY", os.getenv("OPENAI_API_KEY")),
    ("API_KEY", os.getenv("API_KEY")),
    ("DASHSCOPE_API_KEY", os.getenv("DASHSCOPE_API_KEY")),
]:
    if _val:
        _API_KEY_SOURCE = _src
        API_KEY = _val
        break

# ---------------------------------------------------------------------------
# Base URL — 按优先级: DEEPSEEK_BASE_URL > OPENAI_BASE_URL > BASE_URL
# 仅在使用 DEEPSEEK_API_KEY 时启用 DeepSeek 默认值
# ---------------------------------------------------------------------------
_BASE_URL_SOURCE = ""
BASE_URL = ""

for _src, _val in [
    ("DEEPSEEK_BASE_URL", os.getenv("DEEPSEEK_BASE_URL")),
    ("OPENAI_BASE_URL", os.getenv("OPENAI_BASE_URL")),
    ("BASE_URL", os.getenv("BASE_URL")),
]:
    if _val:
        _BASE_URL_SOURCE = _src
        BASE_URL = _val
        break

if not BASE_URL and API_KEY and _API_KEY_SOURCE == "DEEPSEEK_API_KEY":
    BASE_URL = _DEEPSEEK_BASE_URL_DEFAULT
    _BASE_URL_SOURCE = "DEEPSEEK_BASE_URL (默认)"

# ---------------------------------------------------------------------------
# 模型名 — 按优先级: DEEPSEEK_MODEL > OPENAI_MODEL > MODEL_NAME > LLM_MODEL
# 仅在使用 DEEPSEEK_API_KEY 时启用 DeepSeek 默认值
# ---------------------------------------------------------------------------
_MODEL_SOURCE = ""
LLM_MODEL_NAME = ""

for _src, _val in [
    ("DEEPSEEK_MODEL", os.getenv("DEEPSEEK_MODEL")),
    ("OPENAI_MODEL", os.getenv("OPENAI_MODEL")),
    ("MODEL_NAME", os.getenv("MODEL_NAME")),
    ("LLM_MODEL", os.getenv("LLM_MODEL")),
]:
    if _val:
        _MODEL_SOURCE = _src
        LLM_MODEL_NAME = _val
        break

if not LLM_MODEL_NAME and API_KEY and _API_KEY_SOURCE == "DEEPSEEK_API_KEY":
    LLM_MODEL_NAME = _DEEPSEEK_MODEL_DEFAULT
    _MODEL_SOURCE = "DEEPSEEK_MODEL (默认)"

# ---------------------------------------------------------------------------
# Provider 识别
# ---------------------------------------------------------------------------

# 已知的 DeepSeek 模型名称前缀 / 完整名称集合
_DEEPSEEK_MODEL_PATTERNS = ("deepseek",)

# 已知的 DashScope 模型名称前缀
_DASHSCOPE_MODEL_PATTERNS = ("qwen", "dashscope", "tongyi", "bailian")

# DashScope 官方 Base URL 域名
_DASHSCOPE_DOMAINS = ("dashscope.aliyuncs.com", "dashscope-intl.aliyuncs.com")


def _detect_provider() -> str:
    """根据 API Key 来源、Base URL、模型名综合识别 LLM 提供商。

    识别规则（按优先级）:
    1. API Key 来源变量名是最高优先级信号
    2. Base URL 域名作为辅助判断
    3. 模型名称作为兜底判断

    Returns
    -------
    str
        "deepseek" | "openai" | "dashscope" | "custom"
    """
    # 规则 1: API Key 来源变量名（优先级最高）
    if _API_KEY_SOURCE == "DEEPSEEK_API_KEY":
        return "deepseek"
    if _API_KEY_SOURCE == "DASHSCOPE_API_KEY":
        return "dashscope"
    if _API_KEY_SOURCE == "OPENAI_API_KEY":
        return "openai"

    # 规则 2: Base URL 域名
    if BASE_URL:
        domain = _extract_domain(BASE_URL)
        if domain:
            if "api.deepseek.com" in domain:
                return "deepseek"
            if any(ds_domain in domain for ds_domain in _DASHSCOPE_DOMAINS):
                return "dashscope"
            if "api.openai.com" in domain:
                return "openai"

    # 规则 3: 模型名称
    if LLM_MODEL_NAME:
        model_lower = LLM_MODEL_NAME.lower()
        if any(p in model_lower for p in _DEEPSEEK_MODEL_PATTERNS):
            return "deepseek"
        if any(p in model_lower for p in _DASHSCOPE_MODEL_PATTERNS):
            return "dashscope"

    return "custom"


LLM_PROVIDER: str = _detect_provider()


def get_api_key_source() -> str:
    """返回当前 API Key 的来源变量名（供测试和诊断使用）。"""
    return _API_KEY_SOURCE


def get_base_url_source() -> str:
    """返回当前 Base URL 的来源变量名。"""
    return _BASE_URL_SOURCE


def get_model_source() -> str:
    """返回当前模型名的来源变量名。"""
    return _MODEL_SOURCE


# ---------------------------------------------------------------------------
# 文本切分
# ---------------------------------------------------------------------------
CHUNK_SIZE: int = int(os.getenv("CHUNK_SIZE", "500"))
CHUNK_OVERLAP: int = int(os.getenv("CHUNK_OVERLAP", "100"))

# ---------------------------------------------------------------------------
# 租户
# ---------------------------------------------------------------------------
TENANT_ID: str = os.getenv("TENANT_ID", "default")

# ---------------------------------------------------------------------------
# 检索 & 生成
# ---------------------------------------------------------------------------
TOP_K: int = int(os.getenv("TOP_K", "4"))
MAX_CONTEXT_CHARS: int = int(os.getenv("MAX_CONTEXT_CHARS", "8000"))

# ---- Hybrid RAG 3.0: 混合检索 ----
# 向量检索权重 (0.0 ~ 1.0)，关键词权重 = 1 - vector_weight
# 默认 0.7（向量占 70%，关键词占 30%）
RAG_VECTOR_WEIGHT: float = float(os.getenv("RAG_VECTOR_WEIGHT", "0.7"))
RAG_KEYWORD_WEIGHT: float = float(os.getenv("RAG_KEYWORD_WEIGHT", "0.3"))

# 混合检索初始检索数量（融合前每种检索返回的结果数）
HYBRID_FETCH_K: int = int(os.getenv("HYBRID_FETCH_K", "20"))

# ---- Reranker 重排序 ----
RERANK_ENABLE: bool = os.getenv("RERANK_ENABLE", "true").lower() in ("1", "true", "yes")
RERANK_MODEL_NAME: str = os.getenv(
    "RERANK_MODEL_NAME", "BAAI/bge-reranker-base"
)
# Reranker 初始检索数量（送入 reranker 的结果数）
RERANK_FETCH_K: int = int(os.getenv("RERANK_FETCH_K", "20"))
# Reranker 返回的 Top-N 结果数
RERANK_TOP_K: int = int(os.getenv("RERANK_TOP_K", "5"))

# ---- Query Rewrite 查询改写 (Phase 4) ----
QUERY_REWRITE_ENABLE: bool = os.getenv("QUERY_REWRITE_ENABLE", "true").lower() in ("1", "true", "yes")

REQUEST_TIMEOUT: int = int(os.getenv("REQUEST_TIMEOUT", "60"))
TEMPERATURE: float = float(os.getenv("TEMPERATURE", "0.1"))
MAX_RETRIES: int = int(os.getenv("MAX_RETRIES", "2"))
MAX_SOURCE_PREVIEW_CHARS: int = int(os.getenv("MAX_SOURCE_PREVIEW_CHARS", "200"))
REFUSAL_ANSWER: str = os.getenv(
    "REFUSAL_ANSWER",
    "根据当前企业知识库，暂未找到相关信息。"
)

# ---------------------------------------------------------------------------
# 拒答阈值（基于 L2 距离 + 余弦相似度的多层判断）
#
# 评分语义（已校准）:
#   - raw_distance: Chroma L2 距离，越小越相关，归一化向量范围 [0, 2]
#   - relevance_score: 余弦相似度 = 1 - distance²/2，越大越相关，范围 [-1, 1]
#
# 以下阈值基于 2026-07-13 的 12 题评测集校准（初始值，样本量有限）。
# 随着知识库和测试集扩大，应重新校准。
# ---------------------------------------------------------------------------

# 单条结果的 L2 距离上限（超过此距离视为不相关）
# 对于归一化向量:
#   distance=1.0 → cos_sim=0.50
#   distance=1.2 → cos_sim=0.28
#   distance=1.4 → cos_sim=0.02 (几乎不相关)
#
# 基于 2026-07-13 评测数据校准:
#   知识库内 Top 1 raw_distance 范围: [0.7840, 1.0716]
#   知识库外 Top 1 raw_distance 范围: [1.1671, 1.5016]
#   自然分界宽度: 0.0955
#   选取 1.15 作为阈值，处于分界区域内
MAX_RAW_DISTANCE: float = float(os.getenv("MAX_RAW_DISTANCE", "1.15"))

# 单条结果的相关度下限（低于此值视为不相关）
# distance=1.15 → cos_sim≈0.339
#
# 基于 2026-07-13 评测数据校准:
#   知识库内 Top 1 relevance 范围: [0.4258, 0.6927]
#   知识库外 Top 1 relevance 范围: [-0.1275, 0.3189]
#   选取 0.32 作为阈值，低于内部最小值、高于外部最大值
#   [注意] 外部 "Python怎么写快速排序" relevance=0.3189，阈值 0.32 刚好将其拒于门外
MIN_RELEVANCE_SCORE: float = float(os.getenv("MIN_RELEVANCE_SCORE", "0.32"))

# Top 1 与 Top 2 的最小相关度分差
# 基于评测发现: 小知识库（15 chunks）中 Top1/Top2 分差通常极小
#   (范围 0.001~0.017)，强制要求分差导致 7/12 内部问题被误拒。
# 因此默认关闭此检查（设为 0.0），保留参数供大知识库场景启用。
# 如果知识库扩大到数百条以上，可重新评估是否需要此条件。
MIN_TOP1_TOP2_RELEVANCE_GAP: float = float(os.getenv(
    "MIN_TOP1_TOP2_RELEVANCE_GAP", "0.0"
))

# 至少需要的有效片段数（relevance_score >= MIN_RELEVANCE_SCORE 的片段）
MIN_VALID_CHUNKS: int = int(os.getenv("MIN_VALID_CHUNKS", "1"))

# 检索置信度判断使用的 Top N 结果数
CONFIDENCE_TOP_N: int = int(os.getenv("CONFIDENCE_TOP_N", "4"))


# ---------------------------------------------------------------------------
# 辅助函数
# ---------------------------------------------------------------------------


def _mask_key(key: str) -> str:
    """将 API Key 脱敏为 前4...后4 的格式。"""
    if not key:
        return "<not set>"
    if len(key) <= 8:
        return "*" * len(key)
    return key[:4] + "*" * (len(key) - 8) + key[-4:]


def _extract_domain(url: str) -> str:
    """从 URL 中提取域名（不含协议和路径），解析失败返回空字符串。"""
    if not url:
        return ""
    try:
        parsed = urlparse(url)
        return parsed.hostname or ""
    except Exception:
        return ""


def _validate_base_url_format(url: str, issues: list[str]) -> None:
    """检查 Base URL 的基本格式，不泄露完整 URL 内容。"""
    if not isinstance(url, str):
        issues.append("Base URL 格式无效：不是字符串类型")
        return
    url_stripped = url.strip()
    if not url_stripped:
        return  # 空字符串视为未设置
    # 必须包含 scheme
    if "://" not in url_stripped:
        issues.append("Base URL 格式可能有问题：缺少协议头 (https://)")
        return
    try:
        parsed = urlparse(url_stripped)
        if not parsed.hostname:
            issues.append("Base URL 格式可能有问题：无法解析域名")
    except Exception:
        issues.append("Base URL 格式可能有问题：解析失败")


# 已知的 DeepSeek 当前可用模型名称（2026-07 基线，用于校验提示）
_DEEPSEEK_KNOWN_MODELS = {
    "deepseek-chat",
    "deepseek-reasoner",
    "deepseek-v3",
    "deepseek-r1",
    "deepseek-v4-flash",
    "deepseek-v4-pro",
}


def validate_llm_config() -> dict:
    """验证调用大模型所需的配置是否完整且一致。

    仅在需要调用大模型时使用此函数；构建向量库和文档测试不需要。

    校验内容:
    1. API Key 是否已设置
    2. 模型名是否已设置
    3. Base URL 格式是否正确
    4. provider 与 Base URL 一致性
    5. provider 与模型名一致性

    Returns
    -------
    dict
        {"valid": bool, "issues": list[str], "detail": dict}
        detail 中仅包含:
        - provider
        - api_key_source (变量名)
        - base_url_domain (域名)
        - model
    """
    issues: list[str] = []
    provider = LLM_PROVIDER

    # --- 基本存在性检查 ---
    if not API_KEY:
        issues.append("API Key 未设置（检查 DEEPSEEK_API_KEY / OPENAI_API_KEY / API_KEY / DASHSCOPE_API_KEY）")
    if not LLM_MODEL_NAME:
        issues.append("模型名称未设置（检查 DEEPSEEK_MODEL / OPENAI_MODEL / MODEL_NAME / LLM_MODEL）")

    # --- Base URL 格式校验 ---
    if BASE_URL:
        _validate_base_url_format(BASE_URL, issues)

    # --- provider 一致性校验 ---
    base_url_domain = _extract_domain(BASE_URL) if BASE_URL else ""

    # Provider vs Base URL 一致性（只要有 API_KEY 就能判断 provider）
    if API_KEY:
        if provider == "deepseek":
            if base_url_domain and base_url_domain != "api.deepseek.com":
                if any(ds_d in base_url_domain for ds_d in _DASHSCOPE_DOMAINS):
                    issues.append(
                        "配置不一致：provider=deepseek 但 Base URL 指向 DashScope "
                        f"(域名: {base_url_domain})，请检查 DEEPSEEK_BASE_URL / OPENAI_BASE_URL 配置"
                    )
                elif "api.openai.com" in base_url_domain:
                    issues.append(
                        "配置不一致：provider=deepseek 但 Base URL 指向 OpenAI "
                        f"(域名: {base_url_domain})，请检查 Base URL 配置"
                    )
                # 自定义代理（如 127.0.0.1/localhost/内网地址）允许通过

        elif provider == "dashscope":
            if "api.deepseek.com" in base_url_domain:
                issues.append(
                    "配置不一致：provider=dashscope 但 Base URL 指向 DeepSeek "
                    f"(域名: {base_url_domain})，请检查 Base URL 配置"
                )

    # Provider vs 模型名一致性（需要模型名已设置）
    if API_KEY and LLM_MODEL_NAME:
        if provider == "deepseek":
            # 模型名不允许为 qwen 系列
            model_lower = LLM_MODEL_NAME.lower()
            if any(p in model_lower for p in _DASHSCOPE_MODEL_PATTERNS):
                issues.append(
                    f"配置不一致：provider=deepseek 但模型名 '{LLM_MODEL_NAME}' "
                    "为 DashScope/Qwen 系列模型，请检查模型配置"
                )

            # 模型名应是 DeepSeek 已知模型（警告级别，不影响 valid）
            if LLM_MODEL_NAME not in _DEEPSEEK_KNOWN_MODELS:
                if "deepseek" not in model_lower:
                    issues.append(
                        f"警告：provider=deepseek 但模型名 '{LLM_MODEL_NAME}' "
                        "不像是 DeepSeek 已知模型，请确认模型名正确"
                    )

        elif provider == "dashscope":
            # 模型名不得为 deepseek 系列
            model_lower = LLM_MODEL_NAME.lower()
            if any(p in model_lower for p in _DEEPSEEK_MODEL_PATTERNS):
                issues.append(
                    f"配置不一致：provider=dashscope 但模型名 '{LLM_MODEL_NAME}' "
                    "为 DeepSeek 系列模型，请检查模型配置"
                )

    return {
        "valid": len(issues) == 0,
        "issues": issues,
        "detail": {
            "provider": provider,
            "api_key_source": _API_KEY_SOURCE or "<not set>",
            "base_url_domain": base_url_domain or "<not set>",
            "model": LLM_MODEL_NAME or "<not set>",
        },
    }


def overview() -> str:
    """返回可安全打印的配置概览（不包含 API Key 明文）。"""
    lines = [
        "=== RAG 系统配置 ===",
        f"项目根目录 : {PROJECT_ROOT}",
        f"数据目录   : {DATA_DIR}",
        f"向量库目录 : {CHROMA_DIR}",
        f"集合名称   : {COLLECTION_NAME}",
        f"Embedding  : {EMBEDDING_MODEL_NAME}",
        f"Emb Path   : {EMBEDDING_MODEL_PATH or '<not set>'}",
        f"HF Endpoint: {_extract_domain(HF_ENDPOINT) if HF_ENDPOINT else '<not set>'}",
        f"HF Offline : {'yes' if (HF_HUB_OFFLINE or TRANSFORMERS_OFFLINE) else 'no'}",
        f"LLM Provider: {LLM_PROVIDER}",
        f"API Key来源: {_API_KEY_SOURCE or '<not set>'}",
        f"LLM 模型   : {LLM_MODEL_NAME or '<not set>'}",
        f"Base URL   : {_extract_domain(BASE_URL) if BASE_URL else '<not set>'}",
        f"chunk_size : {CHUNK_SIZE}",
        f"overlap    : {CHUNK_OVERLAP}",
        f"top_k      : {TOP_K}",
        f"max_ctx    : {MAX_CONTEXT_CHARS} chars",
        f"vec_weight : {RAG_VECTOR_WEIGHT}",
        f"kw_weight  : {RAG_KEYWORD_WEIGHT}",
        f"rerank_enable: {RERANK_ENABLE}",
        f"rerank_model: {RERANK_MODEL_NAME}",
        f"rerank_topk : {RERANK_TOP_K}",
        f"timeout    : {REQUEST_TIMEOUT}s",
        f"temperature: {TEMPERATURE}",
    ]
    return "\n".join(lines)
