"""BM25 关键词检索器 — 基于分词的关键词匹配

解决 Embedding 向量检索对以下内容容易丢失的问题:
- 专业名词: "ISO9001", "设备编号", "员工编号"
- 精确匹配: 编号、代码、缩写
- 低频专业术语

BM25 算法通过词频(TF)和逆文档频率(IDF)计算文档与查询的相关性，
擅长精确关键词匹配，与向量语义检索互补。

使用 jieba 分词 + rank-bm25 库实现。
"""

from __future__ import annotations

import logging
import pickle
from pathlib import Path
from typing import Optional

from langchain_core.documents import Document

from src.config import CHROMA_DIR, DATA_DIR

logger = logging.getLogger(__name__)

# BM25 索引缓存文件
_BM25_INDEX_FILE = "bm25_index.pkl"
_BM25_DOCS_FILE = "bm25_docs.pkl"


class BM25Retriever:
    """BM25 关键词检索器。

    从 Chroma 向量库中加载所有文档构建 BM25 索引，
    支持与向量检索并行的关键词匹配。

    使用单例模式，首次构建后缓存索引到磁盘。
    """

    def __init__(self):
        self._bm25 = None
        self._documents: list[Document] = []
        self._initialized = False

    # -------------------------------------------------------------------
    # 公开方法
    # -------------------------------------------------------------------

    def ensure_initialized(self) -> None:
        """确保 BM25 索引已初始化（从 Chroma 加载或从缓存恢复）。"""
        if self._initialized:
            return

        cache_dir = CHROMA_DIR

        # 尝试从缓存加载
        if self._load_from_cache(cache_dir):
            self._initialized = True
            logger.info("BM25 索引从缓存加载完成 (docs=%d)", len(self._documents))
            return

        # 从 Chroma 构建索引
        self._build_from_chroma(cache_dir)
        self._initialized = True
        logger.info("BM25 索引构建完成 (docs=%d)", len(self._documents))

    def search(
        self, query: str, top_k: int = 10
    ) -> list[tuple[Document, float]]:
        """BM25 关键词检索。

        Parameters
        ----------
        query : str
            原始查询文本
        top_k : int
            返回结果数

        Returns
        -------
        list[tuple[Document, float]]
            (Document, bm25_score) 列表，按分数降序排列。
            bm25_score 是 BM25 原始分数，越高越相关，无上限。
        """
        self.ensure_initialized()

        if not self._bm25 or not self._documents:
            return []

        import jieba
        tokenized_query = list(jieba.cut(query))
        scores = self._bm25.get_scores(tokenized_query)

        # 按分数降序排列
        indexed_scores = list(enumerate(scores))
        indexed_scores.sort(key=lambda x: x[1], reverse=True)

        results: list[tuple[Document, float]] = []
        for idx, score in indexed_scores[:top_k]:
            if score > 0:  # 只返回有匹配的结果
                results.append((self._documents[idx], float(score)))

        return results

    def get_document_count(self) -> int:
        """获取索引中的文档数量。"""
        return len(self._documents)

    def rebuild(self) -> None:
        """强制重建 BM25 索引（知识库更新后调用）。"""
        self._bm25 = None
        self._documents = []
        self._initialized = False
        cache_dir = CHROMA_DIR
        self._clear_cache(cache_dir)
        self._build_from_chroma(cache_dir)
        self._initialized = True
        logger.info("BM25 索引重建完成 (docs=%d)", len(self._documents))

    # -------------------------------------------------------------------
    # 内部方法
    # -------------------------------------------------------------------

    def _build_from_chroma(self, cache_dir: Path) -> None:
        """从 Chroma 向量库加载所有文档并构建 BM25 索引。"""
        try:
            from src.vector_store import get_chroma_client
            from src.config import COLLECTION_NAME

            client = get_chroma_client()
            collection = client.get_collection(COLLECTION_NAME)

            # 获取所有文档
            result = collection.get(include=["documents", "metadatas"])
        except Exception as e:
            logger.warning("无法从 Chroma 加载文档构建 BM25 索引: %s", e)
            return

        if not result["ids"]:
            logger.warning("Chroma 集合为空，BM25 索引无数据")
            return

        self._documents = []
        import jieba

        corpus: list[list[str]] = []

        for i, doc_id in enumerate(result["ids"]):
            content = result["documents"][i] if result["documents"] else ""
            metadata = result["metadatas"][i] if result["metadatas"] else {}

            doc = Document(page_content=content, metadata=metadata)
            self._documents.append(doc)

            # 分词
            tokenized = list(jieba.cut(content))
            corpus.append(tokenized)

        # 构建 BM25 索引
        from rank_bm25 import BM25Okapi
        self._bm25 = BM25Okapi(corpus)

        # 缓存到磁盘
        self._save_to_cache(cache_dir, corpus)

        logger.info(
            "BM25 索引从 Chroma 构建完成 (docs=%d, vocab=...)",
            len(self._documents),
        )

    def _save_to_cache(self, cache_dir: Path, corpus: list[list[str]]) -> None:
        """将 BM25 索引和文档缓存到磁盘。"""
        try:
            import pickle

            # 保存文档
            docs_data = [
                {"page_content": d.page_content, "metadata": d.metadata}
                for d in self._documents
            ]
            docs_path = cache_dir / _BM25_DOCS_FILE
            with open(docs_path, "wb") as f:
                pickle.dump(docs_data, f)

            # 保存 BM25 索引
            index_path = cache_dir / _BM25_INDEX_FILE
            with open(index_path, "wb") as f:
                pickle.dump(self._bm25, f)

            logger.info("BM25 索引已缓存到 %s", cache_dir)
        except Exception as e:
            logger.warning("BM25 索引缓存失败: %s", e)

    def _load_from_cache(self, cache_dir: Path) -> bool:
        """从磁盘缓存加载 BM25 索引。"""
        import pickle

        docs_path = cache_dir / _BM25_DOCS_FILE
        index_path = cache_dir / _BM25_INDEX_FILE

        if not docs_path.exists() or not index_path.exists():
            return False

        try:
            with open(docs_path, "rb") as f:
                docs_data = pickle.load(f)

            with open(index_path, "rb") as f:
                self._bm25 = pickle.load(f)

            self._documents = [
                Document(
                    page_content=d["page_content"],
                    metadata=d["metadata"],
                )
                for d in docs_data
            ]

            # 验证文档数量一致
            if len(self._documents) != self._bm25.doc_len:
                logger.warning(
                    "BM25 缓存不一致 (docs=%d, index=%s)，将重建",
                    len(self._documents),
                    str(self._bm25.doc_len),
                )
                self._bm25 = None
                self._documents = []
                return False

            return True
        except Exception as e:
            logger.warning("BM25 缓存加载失败: %s，将重建", e)
            self._bm25 = None
            self._documents = []
            return False

    def _clear_cache(self, cache_dir: Path) -> None:
        """清除 BM25 缓存文件。"""
        for fname in (_BM25_INDEX_FILE, _BM25_DOCS_FILE):
            fpath = cache_dir / fname
            if fpath.exists():
                try:
                    fpath.unlink()
                except Exception as e:
                    logger.debug("清除 BM25 缓存文件失败: %s, %s", fpath, e)


# ---------------------------------------------------------------------------
# 单例
# ---------------------------------------------------------------------------

_bm25_retriever: Optional[BM25Retriever] = None


def get_bm25_retriever() -> BM25Retriever:
    """获取全局 BM25 检索器单例。"""
    global _bm25_retriever
    if _bm25_retriever is None:
        _bm25_retriever = BM25Retriever()
    return _bm25_retriever


def clear_bm25_cache() -> None:
    """清除 BM25 检索器缓存（配置变更后调用）。"""
    global _bm25_retriever
    if _bm25_retriever is not None:
        _bm25_retriever.rebuild()
