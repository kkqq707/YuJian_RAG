"""RAG 配置服务 — RAG 3.0 参数管理

提供 RAG 配置的 CRUD 操作：
- 读取当前配置（数据库优先，环境变量兜底）
- 保存/更新配置
- 重置为默认值

单例模式：全局仅一条配置记录 (id=1)。
"""

from __future__ import annotations

import logging
from typing import Optional

from sqlalchemy.orm import Session

from backend.app.database import SessionLocal
from backend.app.models.rag_config import RAGConfig

logger = logging.getLogger(__name__)

# 默认值（与 src/config.py 保持一致）
DEFAULTS = {
    "chunk_size": 500,
    "chunk_overlap": 100,
    "top_k": 4,
    "similarity_threshold": 0.32,
    "hybrid_fetch_k": 20,
    "vector_weight": 0.7,
    "keyword_weight": 0.3,
    "rerank_enable": True,
    "rerank_fetch_k": 20,
    "rerank_top_k": 5,
    "max_raw_distance": 1.15,
    "min_relevance_score": 0.32,
    "query_rewrite_enable": True,
}


def get_rag_config(db: Session | None = None) -> dict:
    """获取当前 RAG 配置。

    数据库优先，环境变量兜底。

    Parameters
    ----------
    db : Session, optional
        数据库会话，不提供时自动创建

    Returns
    -------
    dict
        完整的 RAG 配置字典
    """
    _close = False
    if db is None:
        db = SessionLocal()
        _close = True

    try:
        config = db.query(RAGConfig).filter(RAGConfig.id == 1).first()

        if config:
            result = {
                "id": config.id,
                "chunk_size": config.chunk_size,
                "chunk_overlap": config.chunk_overlap,
                "top_k": config.top_k,
                "similarity_threshold": config.similarity_threshold,
                "hybrid_fetch_k": config.hybrid_fetch_k,
                "vector_weight": config.vector_weight,
                "keyword_weight": config.keyword_weight,
                "rerank_enable": config.rerank_enable,
                "rerank_fetch_k": config.rerank_fetch_k,
                "rerank_top_k": config.rerank_top_k,
                "max_raw_distance": getattr(config, "max_raw_distance", 1.15),
                "min_relevance_score": getattr(config, "min_relevance_score", 0.32),
                "query_rewrite_enable": getattr(config, "query_rewrite_enable", True),
                "updated_at": config.updated_at.isoformat() if config.updated_at else None,
            }
        else:
            # 回退到环境变量 / 默认值
            result = _get_env_defaults()

        return result

    except Exception as e:
        logger.warning("读取 RAG 配置失败，回退到默认值: %s", e)
        return _get_env_defaults()
    finally:
        if _close:
            db.close()


def save_rag_config(data: dict, db: Session | None = None) -> dict:
    """保存或更新 RAG 配置（upsert 语义）。

    Parameters
    ----------
    data : dict
        要更新的配置字段字典（局部更新）
    db : Session, optional

    Returns
    -------
    dict
        更新后的完整配置
    """
    _close = False
    if db is None:
        db = SessionLocal()
        _close = True

    try:
        config = db.query(RAGConfig).filter(RAGConfig.id == 1).first()

        if config is None:
            config = RAGConfig(id=1)
            db.add(config)

        # 局部更新
        updatable_fields = [
            "chunk_size", "chunk_overlap", "top_k",
            "similarity_threshold", "hybrid_fetch_k",
            "vector_weight", "keyword_weight",
            "rerank_enable", "rerank_fetch_k", "rerank_top_k",
            "max_raw_distance", "min_relevance_score",
            "query_rewrite_enable",
        ]

        for field in updatable_fields:
            if field in data:
                setattr(config, field, data[field])

        db.flush()
        db.refresh(config)

        # 同步到 src.config（内存中的运行时配置）
        _sync_to_runtime(config)

        result = {
            "id": config.id,
            "chunk_size": config.chunk_size,
            "chunk_overlap": config.chunk_overlap,
            "top_k": config.top_k,
            "similarity_threshold": config.similarity_threshold,
            "hybrid_fetch_k": config.hybrid_fetch_k,
            "vector_weight": config.vector_weight,
            "keyword_weight": config.keyword_weight,
            "rerank_enable": config.rerank_enable,
            "rerank_fetch_k": config.rerank_fetch_k,
            "rerank_top_k": config.rerank_top_k,
            "max_raw_distance": getattr(config, "max_raw_distance", 1.15),
            "min_relevance_score": getattr(config, "min_relevance_score", 0.32),
            "query_rewrite_enable": getattr(config, "query_rewrite_enable", True),
            "updated_at": config.updated_at.isoformat() if config.updated_at else None,
        }

        logger.info("RAG 配置已更新: %s", {k: data.get(k) for k in updatable_fields if k in data})
        return result

    except Exception as e:
        logger.error("保存 RAG 配置失败: %s", e)
        raise
    finally:
        if _close:
            db.close()


def reset_rag_config(db: Session | None = None) -> dict:
    """重置 RAG 配置为默认值。

    Parameters
    ----------
    db : Session, optional

    Returns
    -------
    dict
    """
    return save_rag_config(DEFAULTS, db=db)


def _get_env_defaults() -> dict:
    """从环境变量获取默认配置。"""
    import os
    from src.config import (
        CHUNK_SIZE, CHUNK_OVERLAP, TOP_K,
        MIN_RELEVANCE_SCORE, RAG_VECTOR_WEIGHT, RAG_KEYWORD_WEIGHT,
        HYBRID_FETCH_K, RERANK_ENABLE, RERANK_FETCH_K, RERANK_TOP_K,
        MAX_RAW_DISTANCE, QUERY_REWRITE_ENABLE,
    )

    return {
        "id": None,
        "chunk_size": CHUNK_SIZE,
        "chunk_overlap": CHUNK_OVERLAP,
        "top_k": TOP_K,
        "similarity_threshold": MIN_RELEVANCE_SCORE,
        "hybrid_fetch_k": HYBRID_FETCH_K,
        "vector_weight": RAG_VECTOR_WEIGHT,
        "keyword_weight": RAG_KEYWORD_WEIGHT,
        "rerank_enable": RERANK_ENABLE,
        "rerank_fetch_k": RERANK_FETCH_K,
        "rerank_top_k": RERANK_TOP_K,
        "max_raw_distance": MAX_RAW_DISTANCE,
        "min_relevance_score": MIN_RELEVANCE_SCORE,
        "query_rewrite_enable": QUERY_REWRITE_ENABLE,
        "updated_at": None,
    }


def _sync_to_runtime(config: RAGConfig) -> None:
    """将数据库配置同步到 src.config 运行时变量。

    使修改立即生效（影响后续请求），无需重启服务。
    """
    try:
        import src.config as cfg
        cfg.CHUNK_SIZE = config.chunk_size
        cfg.CHUNK_OVERLAP = config.chunk_overlap
        cfg.TOP_K = config.top_k
        cfg.MIN_RELEVANCE_SCORE = config.similarity_threshold
        cfg.RAG_VECTOR_WEIGHT = config.vector_weight
        cfg.RAG_KEYWORD_WEIGHT = config.keyword_weight
        cfg.HYBRID_FETCH_K = config.hybrid_fetch_k
        cfg.RERANK_ENABLE = config.rerank_enable
        cfg.RERANK_FETCH_K = config.rerank_fetch_k
        cfg.RERANK_TOP_K = config.rerank_top_k
        cfg.MAX_RAW_DISTANCE = getattr(config, "max_raw_distance", 1.15)
        cfg.MIN_RELEVANCE_SCORE = getattr(config, "min_relevance_score", 0.32)
        cfg.QUERY_REWRITE_ENABLE = getattr(config, "query_rewrite_enable", True)
        # 同步到 query_rewriter 模块
        try:
            from src.query_rewriter import set_query_rewrite_enabled
            set_query_rewrite_enabled(cfg.QUERY_REWRITE_ENABLE)
        except ImportError:
            pass
        logger.debug("RAG 运行时配置已同步")
    except Exception as e:
        logger.warning("RAG 运行时配置同步失败: %s", e)
