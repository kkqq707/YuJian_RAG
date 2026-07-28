"""RAG 配置数据模型 — RAG 3.0 参数配置

保存企业 RAG 检索参数，支持管理员在线调优。
所有配置参数均可通过 API 动态修改，无需重启服务。

配置项:
- chunk_size / chunk_overlap: 文本切分参数
- top_k: 最终返回给 LLM 的片段数
- similarity_threshold: 相似度阈值
- vector_weight / keyword_weight: 混合检索权重
- hybrid_fetch_k: 混合检索初始召回数
- rerank_enable: 是否启用 Reranker
- rerank_fetch_k: Reranker 输入数量
- rerank_top_k: Reranker 输出数量
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import Boolean, Column, DateTime, Float, Integer, String

from backend.app.models.base import Base


class RAGConfig(Base):
    """RAG 检索参数配置。

    数据库单例模式：全局只有一条记录 (id=1)。
    使用 upsert 语义进行保存/更新。
    """

    __tablename__ = "rag_configs"

    id = Column(Integer, primary_key=True, autoincrement=True)

    # ---- 文本切分 ----
    chunk_size = Column(
        Integer, nullable=False, default=500,
        doc="文本切分大小（字符数）"
    )
    chunk_overlap = Column(
        Integer, nullable=False, default=100,
        doc="文本切分重叠（字符数）"
    )

    # ---- 检索 ----
    top_k = Column(
        Integer, nullable=False, default=4,
        doc="最终返回给 LLM 的片段数量"
    )
    similarity_threshold = Column(
        Float, nullable=False, default=0.32,
        doc="相似度阈值（余弦相似度下限）"
    )
    hybrid_fetch_k = Column(
        Integer, nullable=False, default=20,
        doc="混合检索初始召回数"
    )

    # ---- 混合检索权重 ----
    vector_weight = Column(
        Float, nullable=False, default=0.7,
        doc="向量检索权重 (0.0~1.0)"
    )
    keyword_weight = Column(
        Float, nullable=False, default=0.3,
        doc="关键词检索权重 (0.0~1.0)"
    )

    # ---- Reranker ----
    rerank_enable = Column(
        Boolean, nullable=False, default=True,
        doc="是否启用 Reranker 重排序"
    )
    rerank_fetch_k = Column(
        Integer, nullable=False, default=20,
        doc="送入 Reranker 的文档数量"
    )
    rerank_top_k = Column(
        Integer, nullable=False, default=5,
        doc="Reranker 返回的 Top-N 结果数"
    )

    # ---- 拒答阈值 (Phase 2: RAG 配置中心) ----
    max_raw_distance = Column(
        Float, nullable=False, default=1.15,
        doc="L2 距离上限（超过此距离视为不相关）"
    )
    min_relevance_score = Column(
        Float, nullable=False, default=0.32,
        doc="相关度下限（低于此值视为不相关）"
    )

    # ---- Query Rewrite (Phase 4) ----
    query_rewrite_enable = Column(
        Boolean, nullable=False, default=True,
        doc="是否启用查询改写"
    )

    # ---- 元数据 ----
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    def __repr__(self) -> str:
        return (
            f"RAGConfig(id={self.id}, chunk_size={self.chunk_size}, "
            f"top_k={self.top_k}, vector_weight={self.vector_weight}, "
            f"rerank_enable={self.rerank_enable})"
        )
