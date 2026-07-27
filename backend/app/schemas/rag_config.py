"""RAG 配置 Schema — 请求与响应"""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field, field_validator


class RAGConfigResponse(BaseModel):
    """RAG 配置响应。"""

    id: Optional[int] = Field(None, description="配置 ID")
    chunk_size: int = Field(..., description="文本切分大小")
    chunk_overlap: int = Field(..., description="文本切分重叠")
    top_k: int = Field(..., description="返回片段数")
    similarity_threshold: float = Field(..., description="相似度阈值")
    hybrid_fetch_k: int = Field(..., description="混合检索召回数")
    vector_weight: float = Field(..., description="向量检索权重")
    keyword_weight: float = Field(..., description="关键词检索权重")
    rerank_enable: bool = Field(..., description="是否启用 Reranker")
    rerank_fetch_k: int = Field(..., description="Reranker 输入数")
    rerank_top_k: int = Field(..., description="Reranker 输出数")
    max_raw_distance: float = Field(1.15, description="L2 距离上限")
    min_relevance_score: float = Field(0.32, description="相关度下限")
    query_rewrite_enable: bool = Field(True, description="是否启用查询改写")
    updated_at: Optional[str] = Field(None, description="更新时间")


class RAGConfigUpdateRequest(BaseModel):
    """RAG 配置更新请求 — 所有字段可选（局部更新）。"""

    chunk_size: Optional[int] = Field(
        None, ge=100, le=4000, description="文本切分大小 (100-4000)"
    )
    chunk_overlap: Optional[int] = Field(
        None, ge=0, le=1000, description="文本切分重叠 (0-1000)"
    )
    top_k: Optional[int] = Field(
        None, ge=1, le=20, description="返回片段数 (1-20)"
    )
    similarity_threshold: Optional[float] = Field(
        None, ge=0.0, le=1.0, description="相似度阈值 (0.0-1.0)"
    )
    hybrid_fetch_k: Optional[int] = Field(
        None, ge=5, le=100, description="混合检索召回数 (5-100)"
    )
    vector_weight: Optional[float] = Field(
        None, ge=0.0, le=1.0, description="向量检索权重 (0.0-1.0)"
    )
    keyword_weight: Optional[float] = Field(
        None, ge=0.0, le=1.0, description="关键词检索权重 (0.0-1.0)"
    )
    rerank_enable: Optional[bool] = Field(
        None, description="是否启用 Reranker"
    )
    rerank_fetch_k: Optional[int] = Field(
        None, ge=5, le=100, description="Reranker 输入数 (5-100)"
    )
    rerank_top_k: Optional[int] = Field(
        None, ge=1, le=20, description="Reranker 输出数 (1-20)"
    )
    max_raw_distance: Optional[float] = Field(
        None, ge=0.0, le=2.0, description="L2 距离上限 (0.0-2.0)"
    )
    min_relevance_score: Optional[float] = Field(
        None, ge=0.0, le=1.0, description="相关度下限 (0.0-1.0)"
    )
    query_rewrite_enable: Optional[bool] = Field(
        None, description="是否启用查询改写"
    )

    @field_validator("chunk_overlap", mode="after")
    @classmethod
    def validate_overlap(cls, v: Optional[int], info) -> Optional[int]:
        """chunk_overlap 应小于 chunk_size 的合理范围。"""
        return v


class RAGConfigSaveResponse(BaseModel):
    """RAG 配置保存响应。"""

    success: bool = Field(default=True)
    message: str = Field(default="配置已保存")
    config: RAGConfigResponse
