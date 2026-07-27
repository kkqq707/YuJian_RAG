"""Reranker 重排序模型 — 对初步检索结果进行精细重排序

使用 BAAI/bge-reranker-base (Cross-Encoder) 模型:
- 输入: (query, document) 对
- 输出: 相关度分数 (0~1)
- 优势: 与 Bi-Encoder (Embedding) 相比，Cross-Encoder 能同时看到 query 和 document，
  对语义匹配更精确，适合对初检索结果进行精细排序

流程:
  初检索 Top 20 → Reranker → Top 5 → LLM

企业部署级特性:
- 强制 local_files_only=True，禁止访问 HuggingFace
- 启动时加载，全局单例缓存
- 查询过程中禁止重复加载
- 本地模型路径: backend/models/bge-reranker-base/
- 网络不可用时静默降级，不阻塞检索
"""

from __future__ import annotations

import logging
import os
import threading
from typing import Optional

from langchain_core.documents import Document

logger = logging.getLogger(__name__)

# 默认 Reranker 模型名
_DEFAULT_RERANKER_MODEL = "BAAI/bge-reranker-base"

# 模型就绪标志文件
_MODEL_READY_FLAG = ".model_ready"


def _get_reranker_local_path() -> Optional[str]:
    """推断 Reranker 本地模型路径。

    按优先级查找:
    1. backend/models/bge-reranker-base/
    2. models/bge-reranker-base/
    3. EMBEDDING_MODEL_PATH 同级目录
    """
    from pathlib import Path
    from src.config import PROJECT_ROOT, EMBEDDING_MODEL_PATH

    candidates = [
        PROJECT_ROOT / "backend" / "models" / "bge-reranker-base",
        PROJECT_ROOT / "models" / "bge-reranker-base",
    ]

    if EMBEDDING_MODEL_PATH:
        emb_path = Path(EMBEDDING_MODEL_PATH)
        if not emb_path.is_absolute():
            emb_path = PROJECT_ROOT / emb_path
        parent = emb_path.parent
        candidates.insert(0, parent / "bge-reranker-base")

    for candidate in candidates:
        if candidate.exists() and (candidate / "config.json").exists():
            return str(candidate.resolve())

    return None


def _is_local_model_valid(model_path: str) -> bool:
    """检查本地模型目录是否包含有效的模型文件。

    完整模型需包含:
    - .model_ready 标志文件
    - config.json (模型配置)
    - tokenizer.json (分词器)
    - tokenizer_config.json (分词器配置)
    - special_tokens_map.json (特殊 token 映射)
    - model.safetensors 或 pytorch_model.bin (模型权重)
    """
    from pathlib import Path
    path = Path(model_path)
    if not path.exists() or not path.is_dir():
        return False

    ready_flag = path / _MODEL_READY_FLAG
    has_config = (path / "config.json").exists()
    has_tokenizer = (path / "tokenizer.json").exists()
    has_tokenizer_config = (path / "tokenizer_config.json").exists()
    has_special_tokens = (path / "special_tokens_map.json").exists()
    has_weights = (
        (path / "pytorch_model.bin").exists()
        or (path / "model.safetensors").exists()
    )

    return (
        ready_flag.exists()
        and has_config
        and has_tokenizer
        and has_tokenizer_config
        and has_special_tokens
        and has_weights
    )


class Reranker:
    """Cross-Encoder 重排序器 — 完全本地化版本。

    特性:
    - 启动时加载模型，全局单例缓存
    - local_files_only=True，禁止访问 HuggingFace
    - 查询过程中禁止重复加载（线程安全）
    - 模型不可用时静默降级，不阻塞检索

    启动日志格式:
        Reranker:
          model=BAAI/bge-reranker-base
          path=backend/models/bge-reranker-base
          device=cpu
          status=OK
    """

    def __init__(self, model_name: str | None = None):
        """
        Parameters
        ----------
        model_name : str, optional
            Reranker 模型名称或本地路径。
            默认 "BAAI/bge-reranker-base"，优先使用本地模型。
        """
        self._model_name = model_name or _DEFAULT_RERANKER_MODEL
        self._model = None
        self._initialized = False
        self._available = False
        self._model_path: Optional[str] = None
        self._device: str = "cpu"
        self._lock = threading.Lock()  # 防止并发重复加载

    # -------------------------------------------------------------------
    # 公开方法
    # -------------------------------------------------------------------

    def ensure_initialized(self) -> None:
        """确保 Reranker 模型已加载（线程安全）。

        强制使用本地模型，禁止访问 HuggingFace。
        如果本地无模型，设置 _available=False，不阻塞检索。
        """
        if self._initialized:
            return

        with self._lock:
            # 双重检查锁定（DCL）
            if self._initialized:
                return

            self._do_initialize()
            self._initialized = True

    def _do_initialize(self) -> None:
        """实际的初始化逻辑（在锁保护下执行）。

        加载策略:
        1. 检查 backend/models/bge-reranker-base/ 是否存在
        2. 存在 → 从本地加载 (local_files_only=True)
        3. 不存在 → 标记为不可用，不阻塞检索
        """
        # 检测设备
        try:
            import torch
            self._device = "cuda" if torch.cuda.is_available() else "cpu"
        except ImportError:
            self._device = "cpu"

        # 查找本地模型路径
        local_path = _get_reranker_local_path()

        # 打印启动日志头
        print(f"Reranker:")
        print(f"  model={self._model_name}")
        print(f"  path={local_path or '<未找到本地模型>'}")
        print(f"  device={self._device}")

        if not local_path:
            # 本地模型不存在，标记为不可用
            print(f"  status=UNAVAILABLE (本地模型不存在)")
            print(f"  [提示] 运行 python scripts/download_reranker.py 下载模型")
            print(f"  [提示] 或将模型文件放置到 backend/models/bge-reranker-base/")
            logger.warning(
                "Reranker: model=%s path=<not found> device=%s status=UNAVAILABLE",
                self._model_name, self._device,
            )
            self._available = False
            return

        if not _is_local_model_valid(local_path):
            # 诊断缺失哪些文件
            missing = []
            from pathlib import Path as _Path
            _p = _Path(local_path)
            if not (_p / ".model_ready").exists():
                missing.append(".model_ready")
            if not (_p / "config.json").exists():
                missing.append("config.json")
            if not (_p / "tokenizer.json").exists():
                missing.append("tokenizer.json")
            if not (_p / "tokenizer_config.json").exists():
                missing.append("tokenizer_config.json")
            if not (_p / "special_tokens_map.json").exists():
                missing.append("special_tokens_map.json")
            if not ((_p / "model.safetensors").exists() or (_p / "pytorch_model.bin").exists()):
                missing.append("model.safetensors")

            print(f"  status=UNAVAILABLE (本地模型不完整)")
            if missing:
                print(f"  缺失文件: {', '.join(missing)}")
            print(f"  [提示] 运行 python scripts/download_reranker.py 重新下载")
            logger.warning(
                "Reranker: model=%s path=%s device=%s status=INCOMPLETE missing=%s",
                self._model_name, local_path, self._device, missing,
            )
            self._available = False
            return

        self._model_path = local_path

        # ---- 强制离线模式 ----
        # 在加载模型前设置环境变量，确保 huggingface_hub 不会尝试联网
        os.environ["HF_HUB_OFFLINE"] = "1"
        os.environ["TRANSFORMERS_OFFLINE"] = "1"
        os.environ["HF_DATASETS_OFFLINE"] = "1"

        # 加载模型：优先使用 CrossEncoder（兼容性更好），其次 FlagEmbedding
        model_loaded = False

        # 方案 1: sentence-transformers CrossEncoder（兼容最新 transformers）
        try:
            from sentence_transformers import CrossEncoder
            self._model = CrossEncoder(
                local_path,
                max_length=512,
                device=self._device,
                model_kwargs={"local_files_only": True},
            )
            logger.info(
                "Reranker 模型加载完成 (sentence-transformers): path=%s device=%s",
                local_path, self._device,
            )
            self._available = True
            model_loaded = True
        except ImportError:
            logger.debug("sentence-transformers 不可用，尝试 FlagEmbedding")
        except Exception as e:
            logger.warning(
                "sentence-transformers 加载失败: %s。尝试 FlagEmbedding 回退。",
                str(e).split('\n')[0][:150],
            )

        # 方案 2: FlagEmbedding FlagReranker（BGE 官方库，兼容旧版 transformers）
        if not model_loaded:
            try:
                from FlagEmbedding import FlagReranker

                self._model = FlagReranker(
                    local_path,
                    use_fp16=(self._device == "cuda"),
                )
                logger.info(
                    "Reranker 模型加载完成 (FlagEmbedding): path=%s device=%s",
                    local_path, self._device,
                )
                self._available = True
                model_loaded = True

            except ImportError:
                logger.error(
                    "无法加载 Reranker 模型。请安装以下任一库:\n"
                    "  pip install FlagEmbedding\n"
                    "  或\n"
                    "  pip install sentence-transformers"
                )
                self._available = False

            except (OSError, ConnectionError, TimeoutError) as e:
                logger.error(
                    "Reranker 模型加载失败 (网络错误): %s。"
                    "Reranker 将不可用。请确认模型文件完整存在于: %s",
                    str(e).split('\n')[0][:150],
                    local_path,
                )
                self._available = False

            except Exception as e:
                logger.error(
                    "Reranker 模型加载失败 (未知错误): %s。Reranker 将不可用。",
                    str(e).split('\n')[0][:150],
                )
                self._available = False

        # 打印最终状态
        status = "OK" if self._available else "UNAVAILABLE"
        print(f"  status={status}")
        if self._available:
            logger.info(
                "Reranker: model=%s path=%s device=%s status=OK",
                self._model_name, local_path, self._device,
            )

    def rerank(
        self,
        query: str,
        documents: list[Document],
        top_k: int = 5,
    ) -> list[tuple[Document, float]]:
        """对文档列表进行重排序。

        Parameters
        ----------
        query : str
            原始查询文本
        documents : list[Document]
            待重排序的文档列表
        top_k : int
            返回的 Top-N 结果数

        Returns
        -------
        list[tuple[Document, float]]
            (Document, rerank_score) 列表，按分数降序排列。
        """
        self.ensure_initialized()

        if not self.is_available() or not documents:
            # Reranker 不可用，返回原始文档（保持原始顺序并截断至 top_k）
            return [(doc, 0.0) for doc in documents[:top_k]]

        # 构建 (query, document) 对
        pairs = [[query, doc.page_content] for doc in documents]

        try:
            if hasattr(self._model, "compute_score"):
                # FlagEmbedding
                scores = self._model.compute_score(pairs)
                if isinstance(scores, float):
                    scores = [scores]
                if len(pairs) == 1 and not isinstance(scores, list):
                    scores = [scores]
            else:
                # sentence-transformers
                scores = self._model.predict(pairs)
                if hasattr(scores, "tolist"):
                    scores = scores.tolist()

        except Exception as e:
            logger.warning("Reranker 批量计算失败，尝试逐对计算: %s", e)
            scores = []
            for pair in pairs:
                try:
                    if hasattr(self._model, "compute_score"):
                        s = self._model.compute_score(pair)
                        scores.append(float(s) if not isinstance(s, list) else float(s[0]))
                    else:
                        s = self._model.predict([pair])
                        scores.append(float(s[0]) if hasattr(s, "__getitem__") else float(s))
                except Exception as inner_e:
                    logger.debug("Reranker 单对计算失败: %s", inner_e)
                    scores.append(-10.0)

        # 确保 scores 是浮点数列表
        scores = [float(s) if not isinstance(s, (list, tuple)) else float(s[0]) for s in scores]

        # 组合文档和分数
        scored = list(zip(documents, scores))

        # 按分数降序排列
        scored.sort(key=lambda x: x[1], reverse=True)

        return scored[:top_k]

    def is_available(self) -> bool:
        """检查 Reranker 是否可用（模型已加载且就绪）。"""
        if not self._initialized:
            return False
        return self._available and self._model is not None

    @property
    def model_name(self) -> str:
        return self._model_name

    @property
    def model_path(self) -> Optional[str]:
        return self._model_path

    @property
    def device(self) -> str:
        return self._device


# ---------------------------------------------------------------------------
# 单例 — 全局唯一实例，启动时加载，查询时复用
# ---------------------------------------------------------------------------

_reranker: Optional[Reranker] = None
_reranker_lock = threading.Lock()


def get_reranker(model_name: str | None = None) -> Reranker:
    """获取全局 Reranker 单例（线程安全）。

    首次调用时创建实例并加载模型。
    后续调用直接返回已加载的实例，不会重复加载。
    """
    global _reranker
    if _reranker is None:
        with _reranker_lock:
            if _reranker is None:
                _reranker = Reranker(model_name=model_name)
    return _reranker


def init_reranker_at_startup() -> dict:
    """应用启动时初始化 Reranker 并返回状态信息。

    在 FastAPI lifespan 中调用，确保模型在首次请求前已加载。
    如果 Reranker 不可用，不抛出异常，仅返回状态信息。

    Returns
    -------
    dict
        {"model": str, "path": str, "device": str, "status": str, "available": bool}
    """
    reranker = get_reranker()
    reranker.ensure_initialized()

    return {
        "model": reranker.model_name,
        "path": reranker.model_path or "<not found>",
        "device": reranker.device,
        "status": "OK" if reranker.is_available() else "UNAVAILABLE",
        "available": reranker.is_available(),
    }


def clear_reranker_cache() -> None:
    """清除 Reranker 缓存（模型切换时调用）。"""
    global _reranker
    with _reranker_lock:
        if _reranker is not None:
            # 释放模型内存
            if _reranker._model is not None:
                del _reranker._model
            _reranker = None
