"""混合检索器 — 融合向量语义检索与 BM25 关键词检索

算法:
1. 并行执行 Vector Search 和 BM25 Search
2. 分数归一化（Min-Max normalization）
3. 加权融合: final_score = alpha * vector_score + (1-alpha) * bm25_score
4. 去重合并，按融合分数降序排列

默认 alpha=0.7（向量权重 70%，关键词权重 30%）
可通过环境变量 RAG_VECTOR_WEIGHT / RAG_KEYWORD_WEIGHT 或数据库配置调整。
"""

from __future__ import annotations

import logging
from typing import Optional

from langchain_core.documents import Document

from src.vector_store import (
    RetrievalScore,
    similarity_search_with_relevance,
)
from src.bm25_retriever import get_bm25_retriever

logger = logging.getLogger(__name__)


class HybridRetriever:
    """混合检索器 — 融合向量语义检索与 BM25 关键词检索。

    使用 Reciprocal Rank Fusion (RRF) 增强版 + 加权分数融合，
    对企业专业名词（如 ISO9001、设备编号）和语义理解均能兼顾。
    """

    def __init__(
        self,
        vector_weight: float = 0.7,
        top_k: int = 10,
    ):
        """
        Parameters
        ----------
        vector_weight : float
            向量检索权重 (0.0 ~ 1.0)，关键词权重 = 1 - vector_weight。
            默认 0.7（向量占 70%，关键词占 30%）。
        top_k : int
            融合后返回的结果数。
        """
        self.vector_weight = vector_weight
        self.top_k = top_k

    # -------------------------------------------------------------------
    # 公开方法
    # -------------------------------------------------------------------

    def search(
        self,
        query: str,
        top_k: int | None = None,
        vector_weight: float | None = None,
        filter_dict: dict | None = None,
    ) -> list[tuple[Document, "HybridScore"]]:
        """执行混合检索。

        Parameters
        ----------
        query : str
            原始查询文本
        top_k : int, optional
            返回结果数，默认使用 __init__ 值
        vector_weight : float, optional
            向量检索权重，默认使用 __init__ 值
        filter_dict : dict, optional
            Chroma where 过滤条件

        Returns
        -------
        list[tuple[Document, HybridScore]]
            按融合分数降序排列的结果列表
        """
        _top_k = top_k if top_k is not None else self.top_k
        _alpha = vector_weight if vector_weight is not None else self.vector_weight

        # 并行执行两种检索
        # 向量检索 (使用更大的 k 以增加召回)
        vector_k = max(_top_k * 2, 10)
        try:
            vector_results = similarity_search_with_relevance(
                query, k=vector_k, filter_dict=filter_dict
            )
        except Exception as e:
            logger.warning("向量检索失败: %s，仅使用 BM25", e)
            vector_results = []

        # BM25 关键词检索
        try:
            bm25 = get_bm25_retriever()
            bm25_results = bm25.search(query, top_k=vector_k)
        except Exception as e:
            logger.warning("BM25 检索失败: %s，仅使用向量检索", e)
            bm25_results = []

        # 分数归一化
        v_scores = self._normalize_scores(
            [(doc, rs.relevance_score) for doc, rs in vector_results]
        )
        b_scores = self._normalize_scores(bm25_results)

        # 构建索引映射
        doc_index: dict[str, dict] = {}  # key: chunk_id → {doc, v_score, b_score}

        for (doc, rs), norm_score in zip(vector_results, v_scores):
            chunk_id = doc.metadata.get("chunk_id", doc.page_content[:50])
            if chunk_id not in doc_index:
                doc_index[chunk_id] = {
                    "doc": doc,
                    "v_score": norm_score,
                    "b_score": 0.0,
                    "v_raw": rs.relevance_score,
                    "v_distance": rs.raw_distance,
                }
            else:
                doc_index[chunk_id]["v_score"] = max(
                    doc_index[chunk_id]["v_score"], norm_score
                )

        for (doc, bm25_score), norm_score in zip(bm25_results, b_scores):
            chunk_id = doc.metadata.get("chunk_id", doc.page_content[:50])
            if chunk_id not in doc_index:
                doc_index[chunk_id] = {
                    "doc": doc,
                    "v_score": 0.0,
                    "b_score": norm_score,
                    "v_raw": 0.0,
                    "v_distance": 0.0,
                }
            else:
                doc_index[chunk_id]["b_score"] = max(
                    doc_index[chunk_id]["b_score"], norm_score
                )

        # 加权融合
        fused: list[tuple[Document, HybridScore]] = []
        for info in doc_index.values():
            final_score = (
                _alpha * info["v_score"] + (1 - _alpha) * info["b_score"]
            )
            fused.append((
                info["doc"],
                HybridScore(
                    hybrid_score=round(final_score, 6),
                    vector_score=round(info["v_score"], 6),
                    bm25_score=round(info["b_score"], 6),
                    vector_raw=round(info["v_raw"], 6),
                    vector_distance=round(info["v_distance"], 6),
                    alpha=_alpha,
                ),
            ))

        # 按融合分数降序排列
        fused.sort(key=lambda x: x[1].hybrid_score, reverse=True)

        # 截断至 top_k
        return fused[:_top_k]

    # -------------------------------------------------------------------
    # 内部方法
    # -------------------------------------------------------------------

    @staticmethod
    def _normalize_scores(
        results: list[tuple[Document, float]],
    ) -> list[float]:
        """Min-Max 归一化分数到 [0, 1] 区间。

        对于单个结果，返回 [1.0]。
        对于全零分数，返回原值（避免除零）。
        """
        if not results:
            return []

        scores = [s for _, s in results]

        if len(scores) == 1:
            return [1.0] if scores[0] > 0 else [0.0]

        min_s = min(scores)
        max_s = max(scores)

        if max_s == min_s:
            return [0.5] * len(scores)  # 所有分数相同时给中间值

        return [(s - min_s) / (max_s - min_s) for s in scores]


# ---------------------------------------------------------------------------
# 数据类型
# ---------------------------------------------------------------------------


class HybridScore:
    """混合检索的分数详情。

    Attributes
    ----------
    hybrid_score : float
        融合后的最终分数（0~1），越大越相关。
    vector_score : float
        归一化后的向量检索分数（0~1）。
    bm25_score : float
        归一化后的 BM25 分数（0~1）。
    vector_raw : float
        原始向量相关度分数（relevance_score）。
    vector_distance : float
        原始 L2 距离。
    alpha : float
        实际使用的向量权重。
    """

    __slots__ = (
        "hybrid_score", "vector_score", "bm25_score",
        "vector_raw", "vector_distance", "alpha",
    )

    def __init__(
        self,
        hybrid_score: float,
        vector_score: float,
        bm25_score: float,
        vector_raw: float = 0.0,
        vector_distance: float = 0.0,
        alpha: float = 0.7,
    ):
        self.hybrid_score = hybrid_score
        self.vector_score = vector_score
        self.bm25_score = bm25_score
        self.vector_raw = vector_raw
        self.vector_distance = vector_distance
        self.alpha = alpha

    # ---- 数值协议支持（防御性） ----

    def __float__(self) -> float:
        """返回混合分数，允许 float(score) 转换。"""
        return float(self.hybrid_score)

    def __round__(self, ndigits: int | None = None) -> float:
        """支持 round(score, ndigits) 调用，避免 TypeError。"""
        return round(self.hybrid_score, ndigits)

    def __repr__(self) -> str:
        return (
            f"HybridScore(hybrid={self.hybrid_score:.4f}, "
            f"vector={self.vector_score:.4f}, bm25={self.bm25_score:.4f})"
        )
