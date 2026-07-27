"""本地中文 Embedding 模型

基于 BAAI/bge-small-zh-v1.5，自动检测 CUDA/CPU 设备。
使用 functools.lru_cache 缓存模型实例，避免重复加载。

企业离线部署 — 加载策略（仅本地）:
1. EMBEDDING_MODEL_PATH 存在且有效 → 本地路径加载（不访问网络）
2. EMBEDDING_MODEL_PATH 已配置但模型缺失 → 报错提示下载模型
3. Hugging Face 缓存存在 → 离线缓存加载
4. 全部失败 → 明确错误提示

企业部署级特性:
- 禁止运行时访问 huggingface.co（HF_HUB_OFFLINE=1）
- 模型统一存放于 backend/models/ 目录
- 禁止依赖开发机 C:\\Users\\xxx\\.cache 缓存
"""

from __future__ import annotations

import functools
import logging
import os
from pathlib import Path
from typing import Optional

import torch
from langchain_huggingface import HuggingFaceEmbeddings

from src.config import (
    EMBEDDING_MODEL_NAME,
    EMBEDDING_MODEL_PATH,
    HF_ENDPOINT,
    HF_HUB_OFFLINE,
    TRANSFORMERS_OFFLINE,
)

logger = logging.getLogger(__name__)

# BGE 模型查询指令前缀
_BGE_QUERY_INSTRUCTION = "为这个句子生成表示以用于检索相关文章："

# Hugging Face 缓存目录（与 huggingface_hub 库一致）
_HF_CACHE_DIR = os.path.join(os.path.expanduser("~"), ".cache", "huggingface", "hub")

# 模型下载完成标志文件
_MODEL_READY_FLAG = ".model_ready"


# ---------------------------------------------------------------------------
# 公开函数
# ---------------------------------------------------------------------------


def get_embedding_device() -> str:
    """检测当前可用的 Embedding 设备。

    Returns
    -------
    str
        "cuda" 或 "cpu"
    """
    if torch.cuda.is_available():
        return "cuda"
    return "cpu"


def _is_local_model_valid(model_path: str) -> bool:
    """检查本地模型目录是否包含有效的模型文件。

    通过检查关键文件（config.json 和 pytorch_model.bin / model.safetensors）
    以及 .model_ready 标志文件来判断模型是否完整。

    Parameters
    ----------
    model_path : str
        模型目录的绝对或相对路径

    Returns
    -------
    bool
    """
    path = Path(model_path)
    if not path.exists() or not path.is_dir():
        return False

    # 检查 .model_ready 标志文件（下载完成的标记）
    ready_flag = path / _MODEL_READY_FLAG
    if not ready_flag.exists():
        return False

    # 检查关键模型文件
    has_config = (path / "config.json").exists()
    has_weights = (
        (path / "pytorch_model.bin").exists()
        or (path / "model.safetensors").exists()
    )
    has_tokenizer = (
        (path / "tokenizer.json").exists()
        or (path / "tokenizer_config.json").exists()
    )

    if has_config and has_weights and has_tokenizer:
        return True

    # 也接受 sentence_transformers 的 snapshot 子目录结构
    # 有些下载方式会将文件放在子目录中
    for subdir in path.iterdir():
        if subdir.is_dir():
            sub_ready = subdir / _MODEL_READY_FLAG
            sub_config = subdir / "config.json"
            sub_weights = (
                subdir / "pytorch_model.bin" or subdir / "model.safetensors"
            )
            if sub_config.exists() and sub_weights.exists():
                # 迁移标志文件到父目录
                if sub_ready.exists() and not ready_flag.exists():
                    ready_flag.touch()
                return True

    return False


def _download_model_to_local(model_name: str, target_path: str) -> bool:
    """将模型从 Hugging Face 下载到指定的本地目录。

    使用 huggingface_hub.snapshot_download 下载所有模型文件。
    下载完成后创建 .model_ready 标志文件。

    Parameters
    ----------
    model_name : str
        Hugging Face 模型名称，如 "BAAI/bge-small-zh-v1.5"
    target_path : str
        目标目录的绝对路径

    Returns
    -------
    bool
        下载成功返回 True，失败返回 False
    """
    print(f"  [Embedding] 正在下载模型: {model_name}")
    print(f"  [Embedding] 目标路径: {target_path}")

    try:
        from huggingface_hub import snapshot_download

        target_dir = Path(target_path)
        target_dir.mkdir(parents=True, exist_ok=True)

        # 判断是否使用镜像
        endpoint = HF_ENDPOINT if HF_ENDPOINT else None

        snapshot_download(
            repo_id=model_name,
            local_dir=str(target_dir),
            local_dir_use_symlinks=False,
            resume_download=True,
            endpoint=endpoint,
            # 只下载必要的模型文件，跳过 flax/tf/onnx 等无关格式
            ignore_patterns=[
                "*.flax*",
                "*.msgpack",
                "*.h5",
                "*.ot",
                "*.onnx",
                "onnx/*",
                "flax_model.*",
                "tf_model.*",
                "rust_model.*",
            ],
        )

        # 创建下载完成标志
        ready_flag = target_dir / _MODEL_READY_FLAG
        ready_flag.touch()

        print(f"  [Embedding] 模型下载完成: {target_path}")
        logger.info("模型下载完成: %s → %s", model_name, target_path)
        return True

    except Exception as e:
        print(f"  [Embedding] 模型下载失败: {e}")
        logger.error("模型下载失败: %s → %s, 错误: %s", model_name, target_path, e)
        # 清理失败的下载目录（避免残留不完整文件）
        _cleanup_failed_download(target_path)
        return False


def _cleanup_failed_download(target_path: str) -> None:
    """清理下载失败的目录。

    Parameters
    ----------
    target_path : str
        要清理的目录路径
    """
    import shutil

    target_dir = Path(target_path)
    # 仅删除标志文件，保留目录（可能用户手动放置了文件）
    ready_flag = target_dir / _MODEL_READY_FLAG
    if ready_flag.exists():
        ready_flag.unlink()
        logger.info("已移除不完整的模型标志文件: %s", ready_flag)


def _resolve_load_strategy() -> dict:
    """解析 Embedding 模型加载策略，返回描述信息字典。

    企业离线部署：仅支持本地加载，禁止任何网络访问。

    Returns
    -------
    dict
        {"strategy": str, "detail": str, "is_offline": bool, "model_path": str}
        strategy: "local_path" | "local_path_missing" | "cached" | "fallback"
    """
    # 策略 1: EMBEDDING_MODEL_PATH 已配置且存在有效模型 → 本地加载
    if EMBEDDING_MODEL_PATH:
        # 解析为绝对路径（相对于项目根目录）
        from src.config import PROJECT_ROOT
        local_path = Path(EMBEDDING_MODEL_PATH)
        if not local_path.is_absolute():
            local_path = PROJECT_ROOT / local_path
        local_path_str = str(local_path.resolve())

        if _is_local_model_valid(local_path_str):
            return {
                "strategy": "local_path",
                "detail": f"本地加载: {EMBEDDING_MODEL_PATH}",
                "is_offline": True,
                "model_path": local_path_str,
            }

        # 策略 2: EMBEDDING_MODEL_PATH 已配置但模型文件不完整或不存在
        # 离线模式下无法下载，直接报错
        return {
            "strategy": "local_path_missing",
            "detail": (
                f"模型路径已配置 ({EMBEDDING_MODEL_PATH}) "
                "但模型文件缺失或不完整，且离线模式禁止下载"
            ),
            "is_offline": True,
            "model_path": local_path_str,
            "model_path_relative": EMBEDDING_MODEL_PATH,
        }

    # 策略 3: Hugging Face 缓存（兼容旧版部署）
    if _is_model_cached(EMBEDDING_MODEL_NAME):
        return {
            "strategy": "cached",
            "detail": f"已缓存于: {_HF_CACHE_DIR}",
            "is_offline": True,
            "model_path": _HF_CACHE_DIR,
        }

    # 策略 4: 无可用模型
    return {
        "strategy": "fallback",
        "detail": (
            "离线模式：未找到本地模型。"
            "请设置 EMBEDDING_MODEL_PATH 指向模型目录"
        ),
        "is_offline": True,
        "model_path": "",
    }


@functools.lru_cache(maxsize=1)
def get_embedding_model() -> HuggingFaceEmbeddings:
    """获取（并缓存）中文 Embedding 模型实例。

    按分级策略加载：
    1. EMBEDDING_MODEL_PATH 存在 → 本地路径
    2. EMBEDDING_MODEL_PATH 已配置 → 下载到本地目录
    3. Hugging Face 缓存 → 离线加载
    4. HF_ENDPOINT → 镜像下载
    5. 官方 Hugging Face → 在线下载
    6. 全部失败 → 抛出明确错误

    首次调用时可能下载模型文件，后续调用直接返回缓存实例。

    Returns
    -------
    HuggingFaceEmbeddings
    """
    device = get_embedding_device()
    model_name = EMBEDDING_MODEL_NAME

    strategy = _resolve_load_strategy()
    strat_name = strategy["strategy"]
    model_path = strategy.get("model_path", "")

    # ---- 增强的启动日志 ----
    _print_startup_banner(strategy, model_name, device)

    try:
        model = _load_by_strategy(strategy, model_name, device)
    except Exception as e:
        _classify_error(e, model_name, strategy)

    # 用一条简单文本触发模型实际加载
    _ = model.embed_query("加载测试")

    # ---- 加载完成日志 ----
    _print_load_complete(strategy, model_name, device)

    return model


def _print_startup_banner(strategy: dict, model_name: str, device: str) -> None:
    """打印模型加载启动日志（企业离线版）。

    根据加载策略显示不同的日志信息。
    """
    strat_name = strategy["strategy"]
    model_path = strategy.get("model_path", "")
    model_path_rel = strategy.get("model_path_relative", "")

    banner = f"[Embedding] 正在加载中文向量模型: {model_name}（设备: {device}）"
    print(banner)
    logger.info("Embedding 模型加载开始 — 策略: %s, 模型: %s, 设备: %s",
                strat_name, model_name, device)

    if strat_name == "local_path":
        print(f"  [Embedding] 加载方式: 本地加载（离线）")
        print(f"  [Embedding] 模型路径: {model_path_rel or model_path}")
        logger.info("Embedding 模型 — 本地加载 | 路径: %s", model_path)

    elif strat_name == "local_path_missing":
        print(f"  [Embedding] 加载方式: 本地模型缺失")
        print(f"  [Embedding] 配置路径: {model_path_rel or model_path}")
        print(f"  [Embedding] 离线模式禁止下载，请先在有网络环境下载模型")
        logger.warning("Embedding 模型 — 本地模型缺失 | 路径: %s", model_path)

    elif strat_name == "cached":
        print(f"  [Embedding] 加载方式: Hugging Face 缓存（离线）")
        print(f"  [Embedding] 缓存位置: {model_path}")
        print(f"  [Embedding] 建议配置 EMBEDDING_MODEL_PATH 以使用项目本地目录")
        logger.info("Embedding 模型 — 缓存加载 | 缓存: %s", model_path)

    elif strat_name == "fallback":
        print(f"  [Embedding] 加载方式: 离线模式（无可用模型）")
        print(f"  [Embedding] 说明: {strategy['detail']}")


def _print_load_complete(strategy: dict, model_name: str, device: str) -> None:
    """打印模型加载完成日志（企业离线版）。"""
    strat_name = strategy["strategy"]
    model_path = strategy.get("model_path", "")
    model_path_rel = strategy.get("model_path_relative", "")

    log_msg = f"Embedding 模型加载完成: {model_name} (device={device}, strategy={strat_name})"
    logger.info(log_msg)

    if strat_name == "local_path":
        print(f"  [Embedding] [OK] 本地加载成功")
        print(f"  [Embedding] 路径: {model_path_rel or model_path}")
    elif strat_name == "cached":
        print(f"  [Embedding] [OK] 缓存加载成功")
        print(f"  [Embedding] 路径: {model_path}")
    else:
        print(f"  [Embedding] 模型加载完成 (策略: {strat_name})")


# ---------------------------------------------------------------------------
# 加载策略实现
# ---------------------------------------------------------------------------


def _load_by_strategy(
    strategy: dict,
    model_name: str,
    device: str,
) -> HuggingFaceEmbeddings:
    """按指定策略加载 Embedding 模型（仅支持本地加载）。

    企业离线部署：所有策略均设置离线环境变量，
    禁止 huggingface_hub 访问网络。

    Parameters
    ----------
    strategy : dict
        _resolve_load_strategy() 的返回值
    model_name : str
        Hugging Face 模型名称
    device : str
        "cuda" 或 "cpu"

    Returns
    -------
    HuggingFaceEmbeddings
    """
    strat = strategy["strategy"]

    if strat == "local_path":
        model_path = strategy["model_path"]
        _apply_env_for_strategy(strat)
        return HuggingFaceEmbeddings(
            model_name=model_path,
            model_kwargs={"device": device},
            encode_kwargs={"normalize_embeddings": True},
        )

    if strat == "local_path_missing":
        model_path = strategy["model_path"]
        raise RuntimeError(
            f"Embedding 模型未在配置路径找到: {model_path}\n"
            f"  模型: {model_name}\n"
            f"  解决方法:\n"
            f"  1. 在有网络的环境中运行下载脚本获取模型\n"
            f"  2. 或将模型文件手动放置到: {model_path}\n"
            f"  所需文件: config.json, model.safetensors, tokenizer.json,\n"
            f"  tokenizer_config.json, 以及 .model_ready 标志文件"
        )

    if strat == "cached":
        # 解析缓存快照的实际路径
        snapshot_path = _resolve_cache_snapshot_path(model_name)
        if snapshot_path:
            _apply_env_for_strategy("local_path")
            return HuggingFaceEmbeddings(
                model_name=snapshot_path,
                model_kwargs={"device": device},
                encode_kwargs={"normalize_embeddings": True},
            )

        # 缓存目录存在但无快照，尝试用缓存目录名 + 离线环境变量
        cache_dir_path = os.path.join(
            _HF_CACHE_DIR,
            "models--" + model_name.replace("/", "--"),
        )
        if os.path.isdir(cache_dir_path):
            _apply_env_for_strategy(strat)
            return HuggingFaceEmbeddings(
                model_name=cache_dir_path,
                model_kwargs={"device": device},
                encode_kwargs={"normalize_embeddings": True},
            )

        # 不应到达这里（_resolve_load_strategy 已确认缓存存在）
        _apply_env_for_strategy(strat)
        return HuggingFaceEmbeddings(
            model_name=model_name,
            model_kwargs={"device": device},
            encode_kwargs={"normalize_embeddings": True},
            cache_folder=_HF_CACHE_DIR,
        )

    # strat == "fallback" — 离线 + 无模型
    raise RuntimeError(
        f"无法加载 Embedding 模型 '{model_name}'。\n"
        f"  原因: {strategy['detail']}\n"
        f"  建议:\n"
        f"  1. 设置 EMBEDDING_MODEL_PATH=./backend/models/bge-small-zh-v1.5\n"
        f"  2. 确保模型文件完整且 .model_ready 标志存在\n"
        f"  3. 在有网络的环境中运行一次，系统将下载模型到本地"
    )


def _apply_env_for_strategy(strat: str) -> None:
    """设置 huggingface_hub 环境变量 — 企业离线部署始终强制离线。

    所有策略均设置 HF_HUB_OFFLINE=1、TRANSFORMERS_OFFLINE=1，
    禁止运行时访问 huggingface.co。

    Parameters
    ----------
    strat : str
        策略名（保留用于日志记录）
    """
    # 始终强制离线 — 企业部署不允许运行时联网
    os.environ["HF_HUB_OFFLINE"] = "1"
    os.environ["TRANSFORMERS_OFFLINE"] = "1"
    os.environ["HF_DATASETS_OFFLINE"] = "1"
    logger.info("已设置 HF_HUB_OFFLINE=1, TRANSFORMERS_OFFLINE=1 (企业离线部署, 策略: %s)", strat)


def _resolve_cache_snapshot_path(model_name: str) -> str | None:
    """解析 Hugging Face 缓存中模型的实际快照路径。

    在缓存目录中查找模型的最新完整快照，
    返回可直接用于本地加载的绝对路径。

    Parameters
    ----------
    model_name : str
        如 "BAAI/bge-small-zh-v1.5"

    Returns
    -------
    str | None
        快照目录的绝对路径，未找到则返回 None
    """
    cache_dir_name = "models--" + model_name.replace("/", "--")
    cache_path = os.path.join(_HF_CACHE_DIR, cache_dir_name)
    snapshots_dir = os.path.join(cache_path, "snapshots")

    if not os.path.isdir(snapshots_dir):
        return None

    # 找到最新的非空快照
    best_snapshot = None
    best_mtime = 0
    for entry in os.listdir(snapshots_dir):
        snapshot_path = os.path.join(snapshots_dir, entry)
        if os.path.isdir(snapshot_path) and os.listdir(snapshot_path):
            mtime = os.path.getmtime(snapshot_path)
            if mtime > best_mtime:
                best_mtime = mtime
                best_snapshot = snapshot_path

    return best_snapshot


# ---------------------------------------------------------------------------
# 缓存检测
# ---------------------------------------------------------------------------


def _is_model_cached(model_name: str) -> bool:
    """检测 Hugging Face 模型是否已缓存到本地。

    检查 huggingface_hub 的标准缓存目录结构:
    ~/.cache/huggingface/hub/models--{org}--{name}/

    Parameters
    ----------
    model_name : str
        如 "BAAI/bge-small-zh-v1.5"

    Returns
    -------
    bool
    """
    # 标准缓存路径
    cache_dir_name = "models--" + model_name.replace("/", "--")
    cache_path = os.path.join(_HF_CACHE_DIR, cache_dir_name)

    if os.path.isdir(cache_path):
        # 检查 snapshots 目录下是否有实际文件
        snapshots_dir = os.path.join(cache_path, "snapshots")
        if os.path.isdir(snapshots_dir):
            for entry in os.listdir(snapshots_dir):
                snapshot_path = os.path.join(snapshots_dir, entry)
                if os.path.isdir(snapshot_path) and os.listdir(snapshot_path):
                    return True

    # 也检查 HF_HOME / HUGGINGFACE_HUB_CACHE 环境变量指定的目录
    for env_var in ("HF_HOME", "HUGGINGFACE_HUB_CACHE"):
        alt_dir = os.getenv(env_var)
        if alt_dir:
            alt_cache_path = os.path.join(
                alt_dir if env_var == "HUGGINGFACE_HUB_CACHE"
                else os.path.join(alt_dir, "hub"),
                cache_dir_name,
            )
            if os.path.isdir(alt_cache_path):
                snapshots_dir = os.path.join(alt_cache_path, "snapshots")
                if os.path.isdir(snapshots_dir):
                    for entry in os.listdir(snapshots_dir):
                        snapshot_path = os.path.join(snapshots_dir, entry)
                        if os.path.isdir(snapshot_path) and os.listdir(snapshot_path):
                            return True

    return False


def is_model_available_locally() -> bool:
    """公开接口：检查 Embedding 模型是否可离线加载。

    检查顺序:
    1. EMBEDDING_MODEL_PATH 是否配置且存在有效模型
    2. Hugging Face 缓存是否存在

    Returns
    -------
    bool
    """
    if EMBEDDING_MODEL_PATH:
        from src.config import PROJECT_ROOT
        local_path = Path(EMBEDDING_MODEL_PATH)
        if not local_path.is_absolute():
            local_path = PROJECT_ROOT / local_path
        if _is_local_model_valid(str(local_path.resolve())):
            return True
    return _is_model_cached(EMBEDDING_MODEL_NAME)


def get_load_strategy_info() -> dict:
    """获取当前加载策略的详细信息（供诊断使用）。

    Returns
    -------
    dict
        {
            "model_name": str,
            "model_path": str,
            "model_path_configured": bool,
            "model_path_exists": bool,
            "cached": bool,
            "hf_endpoint_configured": bool,
            "hf_endpoint": str,
            "is_offline": bool,
            "strategy": str,
            "load_method": str,
            "detail": str,
        }
    """
    strategy = _resolve_load_strategy()
    strat_name = strategy["strategy"]

    # 解析加载方式的中文描述
    load_method_map = {
        "local_path": "本地加载（离线）",
        "local_path_missing": "本地模型缺失",
        "cached": "Hugging Face 缓存（离线）",
        "fallback": "离线模式（不可用）",
    }

    return {
        "model_name": EMBEDDING_MODEL_NAME,
        "model_path": EMBEDDING_MODEL_PATH or "<未配置>",
        "model_path_configured": bool(EMBEDDING_MODEL_PATH),
        "model_path_exists": (
            _is_local_model_valid(str(_resolve_model_absolute_path()))
            if EMBEDDING_MODEL_PATH else False
        ),
        "cached": _is_model_cached(EMBEDDING_MODEL_NAME),
        "hf_endpoint_configured": bool(HF_ENDPOINT),
        "hf_endpoint": HF_ENDPOINT or "<未设置>",
        "hf_hub_offline": HF_HUB_OFFLINE,
        "transformers_offline": TRANSFORMERS_OFFLINE,
        "is_offline": strategy["is_offline"],
        "strategy": strat_name,
        "load_method": load_method_map.get(strat_name, "未知"),
        "detail": strategy["detail"],
    }


def _resolve_model_absolute_path() -> Path:
    """将 EMBEDDING_MODEL_PATH 解析为绝对路径。

    Returns
    -------
    Path
    """
    from src.config import PROJECT_ROOT
    model_path = Path(EMBEDDING_MODEL_PATH)
    if not model_path.is_absolute():
        model_path = PROJECT_ROOT / model_path
    return model_path.resolve()


def get_embedding_dimension() -> int:
    """获取 Embedding 向量维度。

    对于 BAAI/bge-small-zh-v1.5，固定为 512。

    Returns
    -------
    int
    """
    # BGE small 模型的标准维度
    name_lower = EMBEDDING_MODEL_NAME.lower()
    if "large" in name_lower:
        return 1024
    if "base" in name_lower:
        return 768
    # small 和默认
    return 512


# ---------------------------------------------------------------------------
# 查询处理
# ---------------------------------------------------------------------------


def prepare_query(query: str) -> str:
    """为 BGE 检索模型添加查询指令前缀。

    只对查询使用；文档入库时不得添加此前缀。
    如果已有前缀则不会重复添加。

    Parameters
    ----------
    query : str

    Returns
    -------
    str

    Raises
    ------
    ValueError
        query 为空或仅含空白
    """
    if not query or not query.strip():
        raise ValueError("查询文本不能为空")
    query = query.strip()
    # 避免重复添加前缀
    if query.startswith(_BGE_QUERY_INSTRUCTION):
        return query
    return f"{_BGE_QUERY_INSTRUCTION}{query}"


def test_embedding_model() -> dict:
    """对当前 Embedding 模型执行基本功能测试。

    Returns
    -------
    dict
        {"ok": bool, "dim": int, "sample_doc": str, "sample_query": str, "errors": [...]}
    """
    errors: list[str] = []
    dim: int = 0

    sample_doc = "成都市煜见科技有限公司是一家专注于AI搜索优化的高科技企业，成立于2020年。"
    sample_query = "煜见科技是做什么的？"

    try:
        model = get_embedding_model()

        # 嵌入文档（不添加查询前缀）
        doc_vec = model.embed_documents([sample_doc])
        if not doc_vec or len(doc_vec[0]) == 0:
            errors.append("文档向量为空")
        else:
            dim = len(doc_vec[0])
            # 检查有限性
            if not all(_is_finite(v) for v in doc_vec[0]):
                errors.append("文档向量包含非有限数值")
            # 检查归一化
            norm = sum(v * v for v in doc_vec[0]) ** 0.5
            if not (0.99 <= norm <= 1.01):
                errors.append(f"归一化异常: 范数={norm:.6f}")

        # 嵌入查询（添加查询前缀）
        query_vec = model.embed_query(prepare_query(sample_query))
        if not query_vec or len(query_vec) == 0:
            errors.append("查询向量为空")
        else:
            if not all(_is_finite(v) for v in query_vec):
                errors.append("查询向量包含非有限数值")
            norm = sum(v * v for v in query_vec) ** 0.5
            if not (0.99 <= norm <= 1.01):
                errors.append(f"查询向量归一化异常: 范数={norm:.6f}")

    except Exception as e:
        errors.append(f"模型测试异常: {e}")

    return {
        "ok": len(errors) == 0,
        "dim": dim,
        "sample_doc": sample_doc,
        "sample_query": sample_query,
        "errors": errors,
    }


# ---------------------------------------------------------------------------
# 内部辅助
# ---------------------------------------------------------------------------


def _is_finite(value: float) -> bool:
    """检查浮点数是否为有限值（非 NaN、非 Inf）。"""
    import math
    return not (math.isnan(value) or math.isinf(value))


def _classify_error(
    error: Exception,
    model_name: str,
    strategy: dict | None = None,
) -> None:
    """将模型加载错误分类并给出清晰中文提示。

    参数
    ----
    error : Exception
        原始异常
    model_name : str
        模型名称
    strategy : dict | None
        当前加载策略信息
    """
    msg = str(error).lower()
    strat_name = strategy["strategy"] if strategy else "unknown"

    if any(kw in msg for kw in ("connection", "timeout", "refused", "resolve", "network")):
        raise RuntimeError(
            f"加载模型 '{model_name}' 失败：检测到网络请求。\n"
            f"  当前策略: {strat_name}\n"
            "  说明: 此为企业离线部署，禁止运行时访问网络。\n"
            "  确保模型文件已完整下载到配置的本地路径。\n"
            f"  原始错误: {error}"
        ) from error

    if "ssl" in msg or "certificate" in msg:
        raise RuntimeError(
            f"加载模型 '{model_name}' 失败：SSL 证书验证错误。\n"
            "  此为企业离线部署，不应发起网络请求。\n"
            f"  原始错误: {error}"
        ) from error

    if any(kw in msg for kw in ("space", "disk", "storage", "no space")):
        raise RuntimeError(
            f"加载模型 '{model_name}' 失败：磁盘空间不足。\n"
            f"  原始错误: {error}"
        ) from error

    if any(kw in msg for kw in ("404", "not found", "invalid", "unknown model")):
        raise RuntimeError(
            f"模型 '{model_name}' 不存在或名称错误。\n"
            "  请检查 EMBEDDING_MODEL_NAME 配置是否正确。\n"
            f"  原始错误: {error}"
        ) from error

    # 未识别的错误
    raise RuntimeError(
        f"加载模型 '{model_name}' 时发生未预期错误 (策略: {strat_name})。\n"
        "  此为企业离线部署，请确保模型文件在本地路径中完整可用。\n"
        f"  原始错误: {error}"
    ) from error
