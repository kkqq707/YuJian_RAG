"""Chroma 本地持久化向量数据库

提供向量库的创建、加载、检索功能。
查询前自动调用 prepare_query() 添加 BGE 查询前缀。

评分语义（已校准，2026-07-13）：

- Chroma collection 使用 **L2 距离** (space: "l2")
- Embedding 已归一化 (normalize_embeddings=True)
- langchain-chroma similarity_search_with_score() 返回的是 Chroma 原始 L2 距离
- **raw_distance 越小越相关**

- relevance_score 通过数学公式从 L2 距离推导：
  对于归一化向量: cos_sim = 1 - (distance² / 2)
  relevance_score = cos_sim，范围约 [0, 1]，越大越相关

- 排序方向: relevance_score 降序（或 raw_distance 升序）
"""

from __future__ import annotations

import logging
import shutil
from functools import lru_cache
from pathlib import Path
from typing import List, Optional, Tuple
from dataclasses import dataclass

from langchain_chroma import Chroma
from langchain_core.documents import Document

from src.config import CHROMA_DIR, COLLECTION_NAME, STORAGE_DIR, TOP_K, DATA_DIR, PROJECT_ROOT
from src.embedding_model import get_embedding_model, prepare_query

logger = logging.getLogger(__name__)

# Chroma 必需的持久化文件
_CHROMA_REQUIRED_FILES = ("chroma.sqlite3",)


# ---------------------------------------------------------------------------
# 评分转换 — 公开函数
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class RetrievalScore:
    """一次检索结果的评分信息。

    Attributes
    ----------
    raw_distance : float
        Chroma 返回的原始 L2 距离。**越小越相关**。
        对于归一化向量，范围约 [0.0, 2.0]，典型相关结果在 [0.5, 1.3] 之间。
    relevance_score : float
        从 L2 距离推导的余弦相似度 = 1 - (distance² / 2)。
        **越大越相关**，范围约 [-1.0, 1.0]，对归一化向量典型值在 [0.15, 0.88] 之间。
    """

    raw_distance: float
    relevance_score: float


def distance_to_relevance(distance: float) -> float:
    """将 Chroma L2 距离转换为相关度分数（余弦相似度）。

    转换依据:
      - Chroma 使用 L2 distance space
      - Embedding 模型启用 normalize_embeddings=True，所有向量归一化为单位向量
      - 对于单位向量: cos_sim = 1 - (L2_distance² / 2)
      - 这是精确的数学推导，非经验公式

    Parameters
    ----------
    distance : float
        Chroma 返回的原始 L2 距离

    Returns
    -------
    float
        相关度分数（余弦相似度），范围 [-1.0, 1.0]，
        但实践中归一化向量极少出现负值。
    """
    # cos_sim = 1 - L2²/2  (for normalized vectors)
    cosine_sim = 1.0 - (distance * distance) / 2.0
    return cosine_sim


def relevance_to_distance(relevance: float) -> float:
    """将相关度分数（余弦相似度）反向映射回 L2 距离。

    这是 distance_to_relevance 的逆函数。用于从阈值反推距离范围。

    Parameters
    ----------
    relevance : float
        余弦相似度

    Returns
    -------
    float
        等效 L2 距离
    """
    import math
    # L2 = sqrt(2 * (1 - cos_sim))
    clamped = max(-1.0, min(1.0, relevance))
    return math.sqrt(2.0 * (1.0 - clamped))


def compute_retrieval_scores(
    raw_distances: list[float],
) -> list[RetrievalScore]:
    """批量计算检索评分。

    Parameters
    ----------
    raw_distances : list[float]
        Chroma 返回的原始 L2 距离列表

    Returns
    -------
    list[RetrievalScore]
    """
    return [
        RetrievalScore(
            raw_distance=d,
            relevance_score=distance_to_relevance(d),
        )
        for d in raw_distances
    ]


# ---------------------------------------------------------------------------
# 单例 Chroma PersistentClient — 避免每次请求重新创建
# ---------------------------------------------------------------------------

_chroma_client: object = None


def get_chroma_client() -> object:
    """获取全局复用的 Chroma PersistentClient 单例。

    应用启动时创建一次，后续请求复用同一个客户端实例，
    避免每次过滤检索都重新打开 SQLite 连接。

    Returns
    -------
    chromadb.PersistentClient
    """
    global _chroma_client
    if _chroma_client is None:
        import chromadb
        _chroma_client = chromadb.PersistentClient(path=str(CHROMA_DIR))
        logger.info("Chroma PersistentClient 单例已创建 (path=%s)", CHROMA_DIR)
    return _chroma_client


# ---------------------------------------------------------------------------
# 公开函数 — 向量库生命周期
# ---------------------------------------------------------------------------


def vector_store_exists() -> bool:
    """判断 Chroma 向量库是否已创建（检查目录和实际数据文件）。

    Returns
    -------
    bool
    """
    if not CHROMA_DIR.is_dir():
        return False
    # 至少需要一个 Chroma 数据文件
    for fname in _CHROMA_REQUIRED_FILES:
        if not (CHROMA_DIR / fname).is_file():
            return False
    return True


def get_or_create_collection():
    """获取或创建 Chroma collection（幂等操作）。

    如果 collection 不存在则自动创建，避免因 collection 不存在导致失败。
    应优先使用此函数而非直接调用 client.get_collection()。

    Returns
    -------
    chromadb.Collection
    """
    client = get_chroma_client()
    try:
        return client.get_collection(COLLECTION_NAME)
    except Exception:
        logger.info("Collection '%s' 不存在，自动创建", COLLECTION_NAME)
        return client.create_collection(
            name=COLLECTION_NAME,
            metadata={"hnsw:space": "cosine"},
        )


def create_vector_store(
    documents: list[Document],
    reset: bool = False,
) -> Chroma:
    """创建（或重建）Chroma 向量库。

    Parameters
    ----------
    documents : list[Document]
        切分后的 Document 列表，每个必须有 chunk_id
    reset : bool
        True 时先删除已有向量库再重建

    Returns
    -------
    Chroma

    Raises
    ------
    ValueError
        documents 为空或缺少 chunk_id
    """
    if not documents:
        raise ValueError("documents 不能为空，请先执行文档加载和切分")

    # 校验 chunk_id
    ids = []
    for doc in documents:
        cid = doc.metadata.get("chunk_id")
        if not cid:
            raise ValueError(
                f"Document 缺少 chunk_id，请先执行 split_documents() "
                f"(file_name={doc.metadata.get('file_name', '?')})"
            )
        ids.append(cid)

    if reset:
        reset_vector_store()

    embedding = get_embedding_model()

    vectorstore = Chroma.from_documents(
        documents=documents,
        embedding=embedding,
        collection_name=COLLECTION_NAME,
        persist_directory=str(CHROMA_DIR),
        ids=ids,
    )

    logger.info(
        "向量库创建完成: %d 条记录 → %s (collection=%s)",
        len(documents), CHROMA_DIR, COLLECTION_NAME,
    )
    return vectorstore


def load_vector_store() -> Chroma:
    """加载已持久化的 Chroma 向量库。

    Returns
    -------
    Chroma

    Raises
    ------
    FileNotFoundError
        向量库不存在
    """
    if not vector_store_exists():
        raise FileNotFoundError(
            f"向量库不存在，请先运行:\n"
            f"  python scripts/build_index.py --reset\n"
            f"（预期目录: {CHROMA_DIR}）"
        )

    embedding = get_embedding_model()
    return Chroma(
        collection_name=COLLECTION_NAME,
        embedding_function=embedding,
        persist_directory=str(CHROMA_DIR),
    )


def reset_vector_store() -> None:
    """安全删除 Chroma 向量库。

    多层安全检查防止误删项目关键目录。
    使用 Chroma 原生 API 删除 collection 以避免文件锁问题。
    """
    target = CHROMA_DIR.resolve()
    storage_root = STORAGE_DIR.resolve()
    project_root = PROJECT_ROOT.resolve()
    data_dir = DATA_DIR.resolve()

    # 安全检查：目标必须等于或在 storage 目录内
    try:
        target.relative_to(storage_root)
    except ValueError:
        raise RuntimeError(f"安全拒绝: 目标路径 {target} 不在 {storage_root} 内")

    # 安全检查：不能是项目根目录
    if target == project_root:
        raise RuntimeError(f"安全拒绝: 目标路径是项目根目录 ({target})，禁止删除")

    # 安全检查：不能是 data 目录
    if target == data_dir:
        raise RuntimeError(f"安全拒绝: 目标路径是数据目录 ({target})，禁止删除")

    # 安全检查：不能是 storage 根目录
    if target == storage_root:
        raise RuntimeError(f"安全拒绝: 目标路径是存储根目录 ({target})，禁止删除")

    # 安全检查：只能删除 chroma_db 目录
    if target.name != "chroma_db":
        raise RuntimeError(
            f"安全拒绝: 只允许删除 chroma_db 目录，当前目标: {target.name}"
        )

    # 使用 Chroma API 删除 collection（避免 Windows 文件锁问题）
    # 不再尝试删除 chroma_db 目录本身，因为 Chroma PersistentClient 持有
    # SQLite 文件锁，目录删除在 Windows 上会失败。
    #
    # 策略：通过 API 删除 collection，如果 collection 不存在则视为已清理。
    # 目录保留不删，让 Chroma 管理其内部文件。
    collection_cleared = False
    try:
        client = get_chroma_client()
        try:
            client.delete_collection(COLLECTION_NAME)
            logger.info("已通过 API 删除 collection: %s", COLLECTION_NAME)
            collection_cleared = True
        except Exception as e:
            # collection 不存在也视为已清理（无需删除）
            err_msg = str(e).lower()
            if "does not exist" in err_msg or "not found" in err_msg:
                logger.info("Collection '%s' 不存在，无需删除", COLLECTION_NAME)
                collection_cleared = True
            else:
                logger.debug("API 删除 collection 失败: %s", e)
    except Exception as e:
        logger.warning("无法连接 Chroma 客户端: %s", e)

    # 释放全局 Chroma 客户端单例
    # 确保后续操作创建新的客户端和 collection
    global _chroma_client
    _chroma_client = None

    # 强制垃圾回收，帮助释放 Windows 上的文件句柄
    import gc
    gc.collect()

    if collection_cleared:
        logger.info("向量库 collection 已清理完成")
    else:
        logger.warning("向量库 collection 可能未完全清理，将继续尝试重建")


# ---------------------------------------------------------------------------
# 公开函数 — 检索
# ---------------------------------------------------------------------------


def get_retriever(k: int | None = None):
    """获取 Chroma Retriever。

    Parameters
    ----------
    k : int, optional
        返回结果数，默认 config.TOP_K

    Returns
    -------
    BaseRetriever
    """
    _k = _validate_k(k)
    vectorstore = load_vector_store()
    return vectorstore.as_retriever(
        search_type="similarity",
        search_kwargs={"k": _k},
    )


def similarity_search(
    query: str,
    k: int | None = None,
) -> list[Document]:
    """向量相似度检索（不返回分数)。

    Parameters
    ----------
    query : str
        原始查询文本（会自动添加 BGE 查询前缀）
    k : int, optional
        返回结果数，默认 config.TOP_K

    Returns
    -------
    list[Document]
    """
    _k = _validate_k(k)
    # 动态限制 top_k：不能超过 collection 实际数量
    try:
        client = get_chroma_client()
        collection = client.get_collection(COLLECTION_NAME)
        actual_count = collection.count()
        if _k > actual_count:
            _k = actual_count
        if _k <= 0:
            return []
    except Exception:
        pass
    processed_query = prepare_query(query)
    vectorstore = load_vector_store()
    return vectorstore.similarity_search(processed_query, k=_k)


def similarity_search_with_score(
    query: str,
    k: int | None = None,
) -> list[tuple[Document, float]]:
    """向量检索，返回 (Document, relevance_score)。

    **弃用警告**：此函数保留用于向后兼容。
    新代码应使用 similarity_search_with_raw_distance() 或
    similarity_search_with_relevance()。

    Returns
    -------
    list[tuple[Document, float]]
        (Document, relevance_score) 列表，按相关度降序排列。
        relevance_score 是余弦相似度，范围约 [0, 1]，越大越相关。
    """
    _k = _validate_k(k)
    # 动态限制 top_k：不能超过 collection 实际数量
    try:
        client = get_chroma_client()
        collection = client.get_collection(COLLECTION_NAME)
        actual_count = collection.count()
        if _k > actual_count:
            _k = actual_count
        if _k <= 0:
            return []
    except Exception:
        pass
    processed_query = prepare_query(query)
    vectorstore = load_vector_store()
    # Chroma.similarity_search_with_score 返回的是 L2 距离
    results = vectorstore.similarity_search_with_score(processed_query, k=_k)
    # L2 距离 → 余弦相似度
    scored: list[tuple[Document, float]] = []
    for doc, distance in results:
        scored.append((doc, distance_to_relevance(distance)))
    # 按相关度降序
    scored.sort(key=lambda x: x[1], reverse=True)
    return scored


def similarity_search_with_raw_distance(
    query: str,
    k: int | None = None,
) -> list[tuple[Document, float]]:
    """向量检索，返回原始 L2 距离。

    **raw_distance 越小越相关。**
    这是最底层、无转换的分数，适合用来设定阈值。

    Parameters
    ----------
    query : str
        原始查询文本（会自动添加 BGE 查询前缀）
    k : int, optional
        返回结果数，默认 config.TOP_K

    Returns
    -------
    list[tuple[Document, float]]
        (Document, raw_distance) 列表，按距离升序排列（越小越相关）。
        raw_distance 是 Chroma 的 L2 空间距离，对于归一化向量范围约 [0, 2]。
    """
    _k = _validate_k(k)
    # 动态限制 top_k：不能超过 collection 实际数量
    try:
        client = get_chroma_client()
        collection = client.get_collection(COLLECTION_NAME)
        actual_count = collection.count()
        if _k > actual_count:
            _k = actual_count
        if _k <= 0:
            return []
    except Exception:
        pass
    processed_query = prepare_query(query)
    vectorstore = load_vector_store()
    results = vectorstore.similarity_search_with_score(processed_query, k=_k)
    # 按距离升序排列（越小越相关）
    results.sort(key=lambda x: x[1])
    return results


def similarity_search_with_relevance(
    query: str,
    k: int | None = None,
    filter_dict: dict | None = None,
) -> list[tuple[Document, RetrievalScore]]:
    """向量检索，返回 (Document, RetrievalScore)。

    RetrievalScore 同时包含 raw_distance 和 relevance_score，
    语义明确，推荐使用此函数进行需要分数的检索。

    Parameters
    ----------
    query : str
        原始查询文本（会自动添加 BGE 查询前缀）
    k : int, optional
        返回结果数，默认 config.TOP_K
    filter_dict : dict, optional
        Chroma where 过滤条件，例如 {"tenant_id": "default"}

    Returns
    -------
    list[tuple[Document, RetrievalScore]]
        (Document, RetrievalScore) 列表，按 relevance_score 降序排列（越大越相关）。
    """
    _k = _validate_k(k)
    processed_query = prepare_query(query)
    vectorstore = load_vector_store()

    # 如果提供了过滤条件，使用 Chroma 原生 API 进行过滤查询
    if filter_dict:
        client = get_chroma_client()
        collection = client.get_collection(COLLECTION_NAME)
        # 动态限制 top_k：不能超过 collection 实际数量
        actual_count = collection.count()
        if _k > actual_count:
            _k = actual_count
        if _k <= 0:
            return []
        embedding = get_embedding_model()
        query_embedding = embedding.embed_query(processed_query)
        raw_results = collection.query(
            query_embeddings=[query_embedding],
            n_results=_k,
            where=filter_dict,
            include=["documents", "metadatas", "distances"],
        )
        # 转换为 (Document, distance) 格式
        results = []
        if raw_results["ids"] and raw_results["ids"][0]:
            for i, doc_id in enumerate(raw_results["ids"][0]):
                doc_content = raw_results["documents"][0][i] if raw_results["documents"] else ""
                doc_metadata = raw_results["metadatas"][0][i] if raw_results["metadatas"] else {}
                doc_distance = raw_results["distances"][0][i] if raw_results["distances"] else 0.0
                doc = Document(page_content=doc_content, metadata=doc_metadata)
                results.append((doc, doc_distance))
    else:
        # 动态限制 top_k：不能超过 collection 实际数量
        try:
            client = get_chroma_client()
            collection = client.get_collection(COLLECTION_NAME)
            actual_count = collection.count()
            if _k > actual_count:
                _k = actual_count
            if _k <= 0:
                return []
        except Exception:
            pass
        results = vectorstore.similarity_search_with_score(processed_query, k=_k)

    # 提取原始距离
    raw_distances = [r[1] for r in results]
    # 构建评分
    scored: list[tuple[Document, RetrievalScore]] = []
    for (doc, _distance), rs in zip(results, compute_retrieval_scores(raw_distances)):
        scored.append((doc, rs))
    # 按相关度降序
    scored.sort(key=lambda x: x[1].relevance_score, reverse=True)
    return scored


def similarity_search_with_mmr(
    query: str,
    k: int | None = None,
    fetch_k: int = 8,
    lambda_mult: float = 0.5,
) -> list[tuple[Document, RetrievalScore]]:
    """MMR (Maximal Marginal Relevance) 检索。

    在保持相关性的同时增加结果多样性，减少重复。

    Parameters
    ----------
    query : str
        原始查询文本（会自动添加 BGE 查询前缀）
    k : int, optional
        返回结果数，默认 config.TOP_K
    fetch_k : int
        初始检索数量，从中筛选多样性结果
    lambda_mult : float
        多样性参数：1.0 = 纯相关性，0.0 = 纯多样性

    Returns
    -------
    list[tuple[Document, RetrievalScore]]
    """
    _k = _validate_k(k)
    processed_query = prepare_query(query)
    vectorstore = load_vector_store()
    results = vectorstore.max_marginal_relevance_search(
        processed_query, k=_k, fetch_k=fetch_k, lambda_mult=lambda_mult,
    )
    # MMR 不返回分数，需要单独查询距离
    # 对 MMR 结果重新查询距离以获取分数信息
    scored: list[tuple[Document, RetrievalScore]] = []
    for doc in results:
        # 使用文档内容作为查询来获取自匹配距离
        # 对于 MMR 结果，我们使用 embed_query 来获取距离
        q_embedding = get_embedding_model().embed_query(processed_query)
        d_embedding = get_embedding_model().embed_query(doc.page_content)
        # 计算 L2 距离
        import math
        l2 = math.sqrt(sum((a - b) ** 2 for a, b in zip(q_embedding, d_embedding)))
        scored.append((doc, RetrievalScore(
            raw_distance=l2,
            relevance_score=distance_to_relevance(l2),
        )))
    scored.sort(key=lambda x: x[1].relevance_score, reverse=True)
    return scored


# ---------------------------------------------------------------------------
# 内部辅助
# ---------------------------------------------------------------------------


def _validate_k(k: int | None) -> int:
    """校验 k 参数。"""
    if k is None:
        return TOP_K
    if k <= 0:
        raise ValueError(f"k 必须大于 0，当前值: {k}")
    return k


def _safe_rmtree(target: Path) -> None:
    """安全删除目录树，处理 Chroma 文件锁。

    Chroma 可能持有 SQLite 文件锁，导致首次删除失败。
    最多重试 3 次，间隔递增。
    """
    import time
    max_retries = 3
    for attempt in range(max_retries):
        try:
            shutil.rmtree(target)
            return
        except PermissionError:
            if attempt < max_retries - 1:
                wait = 0.5 * (attempt + 1)
                logger.debug("删除目录失败（文件锁），%0.1fs 后重试…", wait)
                time.sleep(wait)
            else:
                raise RuntimeError(
                    f"无法删除向量库目录（文件可能被锁定）: {target}\n"
                    "  请关闭其他使用该向量库的进程后重试"
                )
