"""RAG 问答服务 3.0 — Hybrid RAG: 混合检索 + Reranker + LLM 生成

RAG 3.0 升级功能:
- 混合检索: Vector Search + BM25 关键词检索 + RRF 融合
- Reranker 重排序: BAAI/bge-reranker-base Cross-Encoder 精细排序
- 检索调试模式: 管理员可查看完整检索链路（Query → 召回 → Rerank → 最终）
- 增强来源信息: 真实文件名、版本号、页码

流程（管理员调试模式）:
  用户问题 → Hybrid Search(Top20) → Reranker(Top5) → Prompt → LLM
              ↓ 向量 + BM25融合       ↓ Cross-Encoder

流程（普通用户模式）:
  用户问题 → Hybrid Search(Top20) → Reranker(Top5) → Prompt → LLM
"""

from __future__ import annotations

import logging
import time
from typing import Optional

from langchain_core.documents import Document
from langchain_core.messages import AIMessage

from src.config import (
    TOP_K,
    MAX_RAW_DISTANCE,
    MIN_RELEVANCE_SCORE,
    MIN_VALID_CHUNKS,
    MAX_SOURCE_PREVIEW_CHARS,
    MAX_CONTEXT_CHARS,
    REFUSAL_ANSWER,
    RAG_VECTOR_WEIGHT,
    RAG_KEYWORD_WEIGHT,
    HYBRID_FETCH_K,
    RERANK_ENABLE,
    RERANK_FETCH_K,
    RERANK_TOP_K,
)
from src.vector_store import (
    load_vector_store,
    RetrievalScore,
    vector_store_exists,
    similarity_search_with_relevance,
)
from src.config import TENANT_ID
from src.retrieval_judge import is_retrieval_confident
from src.prompts import create_rag_prompt, format_context_documents
from src.query_rewriter import rewrite_query, is_query_rewrite_enabled

logger = logging.getLogger(__name__)


class RAGService:
    """企业知识库 RAG 问答服务 3.0。

    负责完整的 Hybrid 检索→Rerank→置信度评估→LLM 生成→来源构建流程。
    LLM 延迟加载，避免仅测试检索时调用 API。
    """

    def __init__(self):
        """初始化 RAG 服务，加载向量库但不连接 LLM。"""
        if not vector_store_exists():
            raise FileNotFoundError(
                "向量库不存在，请先运行：\n"
                "  python scripts/build_index.py --reset"
            )
        self._vectorstore = load_vector_store()
        self._llm = None  # 延迟加载
        self._hybrid_retriever = None  # 延迟加载
        self._reranker = None  # 延迟加载

    # -----------------------------------------------------------------------
    # 公开方法
    # -----------------------------------------------------------------------

    def ask(
        self,
        question: str,
        user_mode: bool = True,
        debug: bool = False,
    ) -> dict:
        """完成一次完整的 RAG 3.0 问答。

        流程: Hybrid Search → Rerank → Confidence → Context → LLM → Sources

        Parameters
        ----------
        question : str
            用户的原始问题
        user_mode : bool
            True 使用普通用户 Prompt，False 使用管理员 Prompt
        debug : bool
            True 时返回完整检索调试信息（检索链路、分数变化等）

        Returns
        -------
        dict
        """
        t0 = time.perf_counter()

        # 性能计时器
        retrieval_time = 0.0
        rerank_time = 0.0
        llm_time = 0.0

        result = {
            "question": question,
            "answer": "",
            "refused": False,
            "refusal_reason": None,
            "retrieval_confident": True,
            "retrieved_count": 0,
            "reranked_count": 0,
            "used_context_count": 0,
            "sources": [],
            "model": None,
            "latency_seconds": 0.0,
            "embedding_seconds": 0.0,
            "retrieval_seconds": 0.0,
            "rerank_seconds": 0.0,
            "llm_seconds": 0.0,
            # Debug 字段
            "debug_info": None,
        }

        # 1. 校验问题
        if not question or not question.strip():
            result["answer"] = REFUSAL_ANSWER
            result["refused"] = True
            result["refusal_reason"] = "问题为空"
            result["retrieval_confident"] = False
            result["latency_seconds"] = round(time.perf_counter() - t0, 3)
            return result

        # 1.5 Query Rewrite (Phase 4: 查询改写)
        rewritten_question = question
        if is_query_rewrite_enabled():
            try:
                rewritten_question = rewrite_query(question, use_llm=False)
                if rewritten_question != question:
                    logger.info("Query Rewrite: '%s' → '%s'", question, rewritten_question)
            except Exception as e:
                logger.debug("Query Rewrite 跳过: %s", str(e)[:80])
                rewritten_question = question

        # 2. Hybrid 混合检索（使用改写后的查询）
        try:
            ret_start = time.perf_counter()
            retrieved = self.hybrid_retrieve(rewritten_question)
            retrieval_time = round(time.perf_counter() - ret_start, 3)
        except Exception as e:
            result["answer"] = REFUSAL_ANSWER
            result["refused"] = True
            result["refusal_reason"] = f"检索失败: {_safe_str(e)}"
            result["retrieval_confident"] = False
            result["latency_seconds"] = round(time.perf_counter() - t0, 3)
            return result

        result["retrieved_count"] = len(retrieved)
        result["retrieval_seconds"] = retrieval_time
        result["embedding_seconds"] = retrieval_time  # embedding 包含在检索时间内

        # Debug: 记录初始检索结果
        debug_initial = None
        if debug:
            # 分别统计 vector 和 bm25 的召回数量
            v_count = sum(1 for _, score in retrieved if getattr(score, 'vector_score', 0) > 0)
            b_count = sum(1 for _, score in retrieved if getattr(score, 'bm25_score', 0) > 0)
            debug_initial = [
                {
                    "rank": i + 1,
                    "file_name": _safe_file_name(doc.metadata.get("file_name", "")),
                    "chunk_id": doc.metadata.get("chunk_id", ""),
                    "content_preview": doc.page_content.strip()[:150],
                    "hybrid_score": round(getattr(score, "hybrid_score", 0), 6),
                    "vector_score": round(getattr(score, "vector_score", 0), 6),
                    "bm25_score": round(getattr(score, "bm25_score", 0), 6),
                }
                for i, (doc, score) in enumerate(retrieved)
            ]

        # 3. Reranker 重排序
        reranked = retrieved
        if RERANK_ENABLE and len(retrieved) > RERANK_TOP_K:
            try:
                rerank_start = time.perf_counter()
                reranked = self.rerank(rewritten_question, retrieved)
                rerank_time = round(time.perf_counter() - rerank_start, 3)
                result["reranked_count"] = len(reranked)
            except Exception as e:
                logger.warning("Reranker 失败，使用原始检索结果: %s", _safe_str(e))
                reranked = retrieved
                result["reranked_count"] = 0
        else:
            result["reranked_count"] = len(reranked)

        result["rerank_seconds"] = rerank_time

        # Debug: 记录 rerank 后结果
        debug_reranked = None
        if debug:
            debug_reranked = [
                {
                    "rank": i + 1,
                    "file_name": _safe_file_name(doc.metadata.get("file_name", "")),
                    "chunk_id": doc.metadata.get("chunk_id", ""),
                    "content_preview": doc.page_content.strip()[:150],
                    "rerank_score": round(score, 4) if isinstance(score, (int, float)) else None,
                }
                for i, (doc, score) in enumerate(reranked)
            ]

        # 4. 置信度评估（基于 reranked 后的结果）
        # 将 reranked 结果转换为 RetrievalScore 格式用于评估
        assessment_results = self._convert_to_retrieval_format(reranked)
        assessment = self.assess_retrieval(assessment_results)
        result["retrieval_confident"] = assessment["confident"]

        if not assessment["confident"]:
            result["answer"] = REFUSAL_ANSWER
            result["refused"] = True
            result["refusal_reason"] = assessment["reason"]
            result["used_context_count"] = 0
            result["sources"] = []
            result["latency_seconds"] = round(time.perf_counter() - t0, 3)
            if debug:
                v_count = sum(1 for d in debug_initial if d["vector_score"] > 0) if debug_initial else 0
                b_count = sum(1 for d in debug_initial if d["bm25_score"] > 0) if debug_initial else 0
                result["debug_info"] = {
                    "query": question,
                    "query_rewrite": rewritten_question if rewritten_question != question else None,
                    "retrieval_stats": {
                        "vector_recall_count": v_count,
                        "bm25_recall_count": b_count,
                        "fusion_total": len(retrieved),
                        "reranker_input_count": min(len(retrieved), RERANK_FETCH_K),
                        "reranker_output_count": len(reranked) if reranked else 0,
                        "final_context_count": 0,
                    },
                    "initial_results": debug_initial,
                    "reranked_results": debug_reranked,
                    "final_results": [],
                    "refused": True,
                    "refusal_reason": assessment["reason"],
                    "config": {
                        "vector_weight": RAG_VECTOR_WEIGHT,
                        "keyword_weight": RAG_KEYWORD_WEIGHT,
                        "rerank_enabled": RERANK_ENABLE,
                        "fetch_k": RERANK_FETCH_K,
                        "rerank_top_k": RERANK_TOP_K,
                        "max_raw_distance": MAX_RAW_DISTANCE,
                        "min_relevance_score": MIN_RELEVANCE_SCORE,
                    },
                }
            return result

        # 5. 选择上下文文档
        context_docs = self.select_context_documents_from_reranked(reranked)
        result["used_context_count"] = len(context_docs)

        # 6. 构建上下文
        context = self.build_context_from_reranked(context_docs, user_mode=user_mode)

        # 7. 调用 LLM 生成答案
        try:
            llm_start = time.perf_counter()
            answer, model_used = self.generate_answer(question, context, user_mode=user_mode)
            llm_time = round(time.perf_counter() - llm_start, 3)
        except Exception as e:
            result["answer"] = REFUSAL_ANSWER
            result["refused"] = True
            result["refusal_reason"] = f"LLM 调用失败: {_safe_str(e)}"
            result["retrieval_confident"] = True
            result["latency_seconds"] = round(time.perf_counter() - t0, 3)
            return result

        result["answer"] = answer
        result["refused"] = False
        result["model"] = model_used
        result["llm_seconds"] = llm_time

        # 8. 构建来源（增强版：包含版本、真实文件名）
        result["sources"] = self.build_sources_enhanced(context_docs)

        result["latency_seconds"] = round(time.perf_counter() - t0, 3)

        # Debug 信息
        if debug:
            # 统计各阶段数量
            v_count = sum(1 for d in debug_initial if d["vector_score"] > 0) if debug_initial else 0
            b_count = sum(1 for d in debug_initial if d["bm25_score"] > 0) if debug_initial else 0

            debug_final = [
                {
                    "rank": i + 1,
                    "file_name": _safe_file_name(doc.metadata.get("file_name", "")),
                    "chunk_id": doc.metadata.get("chunk_id", ""),
                    "version": doc.metadata.get("version", "v1"),
                    "page": doc.metadata.get("page", 1),
                    "content_preview": doc.page_content.strip()[:200],
                }
                for i, (doc, _score) in enumerate(context_docs)
            ]
            result["debug_info"] = {
                "query": question,
                "query_rewrite": rewritten_question if rewritten_question != question else None,
                # 各阶段统计
                "retrieval_stats": {
                    "vector_recall_count": v_count,
                    "bm25_recall_count": b_count,
                    "fusion_total": len(retrieved),
                    "reranker_input_count": min(len(retrieved), RERANK_FETCH_K),
                    "reranker_output_count": len(reranked),
                    "final_context_count": len(context_docs),
                },
                "initial_results": debug_initial,
                "reranked_results": debug_reranked,
                "final_results": debug_final,
                "refused": False,
                "config": {
                    "vector_weight": RAG_VECTOR_WEIGHT,
                    "keyword_weight": RAG_KEYWORD_WEIGHT,
                    "rerank_enabled": RERANK_ENABLE,
                    "fetch_k": RERANK_FETCH_K,
                    "rerank_top_k": RERANK_TOP_K,
                    "max_raw_distance": MAX_RAW_DISTANCE,
                    "min_relevance_score": MIN_RELEVANCE_SCORE,
                },
            }

        # 性能日志
        logger.info(
            "RAG 3.0: retrieval %.1fs | rerank %.1fs | LLM %.1fs | "
            "total %.1fs | hybrid=%d reranked=%d final=%d",
            retrieval_time,
            rerank_time,
            llm_time,
            result["latency_seconds"],
            result["retrieved_count"],
            result["reranked_count"],
            result["used_context_count"],
        )

        return result

    # -----------------------------------------------------------------------
    # Hybrid Search
    # -----------------------------------------------------------------------

    def hybrid_retrieve(
        self, question: str
    ) -> list[tuple[Document, any]]:
        """Hybrid 混合检索：向量 + BM25。

        使用 HybridRetriever 进行融合检索。

        Parameters
        ----------
        question : str
            原始查询文本

        Returns
        -------
        list[tuple[Document, HybridScore]]
            按融合分数降序排列的结果
        """
        if self._hybrid_retriever is None:
            from src.hybrid_retriever import HybridRetriever
            self._hybrid_retriever = HybridRetriever(
                vector_weight=RAG_VECTOR_WEIGHT,
                top_k=HYBRID_FETCH_K,
            )

        filter_dict = {"tenant_id": TENANT_ID}

        # [RAG QUERY] 获取 collection 信息并动态限制 top_k
        try:
            from src.vector_store import get_chroma_client
            from src.config import COLLECTION_NAME
            client = get_chroma_client()
            collection = client.get_collection(COLLECTION_NAME)
            actual_count = collection.count()
        except Exception:
            actual_count = 0

        requested_top_k = HYBRID_FETCH_K
        actual_top_k = min(requested_top_k, actual_count) if actual_count > 0 else requested_top_k

        logger.info(
            "[RAG QUERY] collection: %s | count: %d | requested_top_k: %d | actual_top_k: %d",
            COLLECTION_NAME, actual_count, requested_top_k, actual_top_k,
        )

        results = self._hybrid_retriever.search(
            question,
            top_k=actual_top_k,
            vector_weight=RAG_VECTOR_WEIGHT,
            filter_dict=filter_dict,
        )

        logger.info("[RAG QUERY] result_count: %d", len(results))

        return results

    def retrieve(self, question: str) -> list[tuple[Document, RetrievalScore]]:
        """向后兼容：纯向量检索（旧接口）。

        Parameters
        ----------
        question : str
            原始查询文本

        Returns
        -------
        list[tuple[Document, RetrievalScore]]
        """
        return self.hybrid_retrieve(question) if False else self._pure_vector_retrieve(question)

    def _pure_vector_retrieve(
        self, question: str
    ) -> list[tuple[Document, RetrievalScore]]:
        """纯向量检索（向后兼容旧接口）。"""
        if not question or not question.strip():
            return []

        filter_dict = {"tenant_id": TENANT_ID}
        results = similarity_search_with_relevance(
            question, k=TOP_K, filter_dict=filter_dict
        )

        seen: set[str] = set()
        deduped: list[tuple[Document, RetrievalScore]] = []
        for doc, score in results:
            key = doc.page_content.strip()
            if key in seen:
                continue
            seen.add(key)
            deduped.append((doc, score))

        deduped.sort(key=lambda x: x[1].relevance_score, reverse=True)
        return deduped

    # -----------------------------------------------------------------------
    # Reranker
    # -----------------------------------------------------------------------

    def rerank(
        self,
        question: str,
        results: list[tuple[Document, any]],
    ) -> list[tuple[Document, float]]:
        """使用 Reranker 对检索结果进行精细重排序。

        Parameters
        ----------
        question : str
            原始查询文本
        results : list[tuple[Document, any]]
            初检索结果

        Returns
        -------
        list[tuple[Document, float]]
            (Document, rerank_score) 按分数降序排列
        """
        if self._reranker is None:
            from src.reranker import get_reranker
            self._reranker = get_reranker()

        docs = [doc for doc, _ in results[:RERANK_FETCH_K]]
        reranked = self._reranker.rerank(question, docs, top_k=RERANK_TOP_K)
        return reranked

    # -----------------------------------------------------------------------
    # 置信度评估
    # -----------------------------------------------------------------------

    def assess_retrieval(
        self, results: list[tuple[Document, RetrievalScore]]
    ) -> dict:
        """评估检索结果是否可信。"""
        confident, reason = is_retrieval_confident(results)
        return {"confident": confident, "reason": reason}

    # -----------------------------------------------------------------------
    # 上下文文档选择
    # -----------------------------------------------------------------------

    def select_context_documents(
        self, results: list[tuple[Document, RetrievalScore]]
    ) -> list[tuple[Document, RetrievalScore]]:
        """向后兼容：从纯向量检索结果中选择上下文文档。"""
        valid: list[tuple[Document, RetrievalScore]] = []
        seen: set[str] = set()

        for doc, rs in results:
            if rs.raw_distance > MAX_RAW_DISTANCE:
                continue
            if rs.relevance_score < MIN_RELEVANCE_SCORE:
                continue
            content_key = doc.page_content.strip()
            if content_key in seen:
                continue
            seen.add(content_key)
            valid.append((doc, rs))

        if len(valid) > TOP_K:
            valid = valid[:TOP_K]

        return valid

    def select_context_documents_from_reranked(
        self, reranked: list[tuple[Document, float]]
    ) -> list[tuple[Document, float]]:
        """从 Reranked 结果中选择上下文文档。

        仅做去重，不应用阈值过滤（reranker 已经排序）。
        """
        valid: list[tuple[Document, float]] = []
        seen: set[str] = set()

        for doc, score in reranked:
            content_key = doc.page_content.strip()
            if content_key in seen:
                continue
            seen.add(content_key)
            valid.append((doc, score))

        # 上限 TOP_K
        if len(valid) > TOP_K:
            valid = valid[:TOP_K]

        return valid

    def build_context(
        self,
        documents: list[tuple[Document, RetrievalScore]],
        user_mode: bool = True,
    ) -> str:
        """向后兼容：构建上下文。"""
        if not documents:
            return "（无可用上下文）"

        docs = []
        scores = []
        for doc, rs in documents:
            doc_copy = Document(
                page_content=doc.page_content,
                metadata={**doc.metadata, "relevance_score": rs.relevance_score},
            )
            docs.append(doc_copy)
            scores.append(rs.relevance_score)

        return format_context_documents(docs, relevance_scores=scores, user_mode=user_mode)

    def build_context_from_reranked(
        self,
        documents: list[tuple[Document, float]],
        user_mode: bool = True,
    ) -> str:
        """从 Reranked 结果构建上下文。

        Reranker 分数作为相关度分数传递给格式化函数。
        """
        if not documents:
            return "（无可用上下文）"

        docs = []
        scores = []
        for doc, rerank_score in documents:
            # 安全提取数值分数（支持 HybridScore 等对象）
            numeric_score = _safe_float(rerank_score, default=0.0)
            doc_copy = Document(
                page_content=doc.page_content,
                metadata={
                    **doc.metadata,
                    "relevance_score": max(0.0, min(1.0, (numeric_score + 10) / 20)),
                },
            )
            docs.append(doc_copy)
            scores.append(numeric_score)

        return format_context_documents(docs, relevance_scores=scores, user_mode=user_mode)

    # -----------------------------------------------------------------------
    # LLM 生成
    # -----------------------------------------------------------------------

    def generate_answer(
        self, question: str, context: str, user_mode: bool = True
    ) -> tuple[str, str]:
        """使用 LLM 生成答案。"""
        if self._llm is None:
            from src.llm_client import get_llm
            self._llm = get_llm()

        prompt = create_rag_prompt(user_mode=user_mode)
        messages = prompt.invoke({"context": context, "question": question})

        try:
            response = self._llm.invoke(messages)
        except Exception as e:
            from src.llm_client import sanitize_llm_error
            raise RuntimeError(sanitize_llm_error(e)) from e

        if isinstance(response, AIMessage):
            content = response.content
        elif hasattr(response, "content"):
            content = response.content
        else:
            content = str(response)

        if not content or not str(content).strip():
            raise RuntimeError("模型返回了空响应，请稍后重试")

        model_name = _get_active_model_name()
        try:
            if hasattr(self._llm, "model_name") and self._llm.model_name:
                model_name = self._llm.model_name
            elif hasattr(self._llm, "model") and self._llm.model:
                model_name = self._llm.model
        except Exception:
            pass
        return str(content).strip(), model_name or "unknown"

    # -----------------------------------------------------------------------
    # 来源构建
    # -----------------------------------------------------------------------

    def build_sources(
        self, documents: list[tuple[Document, RetrievalScore]]
    ) -> list[dict]:
        """向后兼容：构建来源信息。"""
        sources = []
        for rank, (doc, rs) in enumerate(documents, start=1):
            file_name = _safe_file_name(doc.metadata.get("file_name", "未知文件"))
            content = doc.page_content.strip()
            import re
            content_clean = re.sub(r"\s+", " ", content)
            preview = content_clean[:MAX_SOURCE_PREVIEW_CHARS]

            sources.append({
                "rank": rank,
                "file_name": file_name,
                "version": doc.metadata.get("version", "v1"),
                "page": doc.metadata.get("page", 1),
                "chunk_id": doc.metadata.get("chunk_id", "未知"),
                "raw_distance": round(rs.raw_distance, 6),
                "relevance_score": round(rs.relevance_score, 6),
                "content_preview": preview,
            })

        return sources

    def build_sources_enhanced(
        self, documents: list[tuple[Document, float]]
    ) -> list[dict]:
        """增强版来源构建 — 包含版本号、真实文件名、页码。

        Parameters
        ----------
        documents : list[tuple[Document, float]]
            Reranked 结果

        Returns
        -------
        list[dict]
        """
        sources = []
        for rank, (doc, rerank_score) in enumerate(documents, start=1):
            file_name = _safe_file_name(doc.metadata.get("file_name", "未知文件"))
            version = doc.metadata.get("version", "v1")
            page = doc.metadata.get("page", 1)

            content = doc.page_content.strip()
            import re
            content_clean = re.sub(r"\s+", " ", content)
            preview = content_clean[:MAX_SOURCE_PREVIEW_CHARS]

            # 安全提取数值分数
            numeric_score = _safe_float(rerank_score, default=0.0)

            sources.append({
                "rank": rank,
                "file_name": file_name,
                "version": version if version else "v1",
                "page": page if isinstance(page, int) else 1,
                "chunk_id": doc.metadata.get("chunk_id", "未知"),
                "rerank_score": round(numeric_score, 4),
                "content_preview": preview,
            })

        return sources

    # -----------------------------------------------------------------------
    # 内部辅助
    # -----------------------------------------------------------------------

    def _convert_to_retrieval_format(
        self, results: list[tuple[Document, any]]
    ) -> list[tuple[Document, RetrievalScore]]:
        """将 reranked/scored 结果转换为 RetrievalScore 格式用于置信度评估。

        对于 reranker 分数，映射到近似 relevance_score。
        """
        converted = []
        for doc, score in results:
            if isinstance(score, RetrievalScore):
                converted.append((doc, score))
            else:
                # 安全提取数值分数
                numeric_score = _safe_float(score, default=0.0)
                # Reranker 分数大致映射: [-10, 10] → [0, 1]
                normalized = max(0.0, min(1.0, (numeric_score + 10) / 20))
                converted.append((
                    doc,
                    RetrievalScore(
                        raw_distance=0.0,  # reranker 无 L2 距离
                        relevance_score=normalized,
                    ),
                ))
        return converted


# ---------------------------------------------------------------------------
# 内部辅助
# ---------------------------------------------------------------------------


def _safe_str(exc: Exception) -> str:
    """从异常中提取安全的一行摘要。"""
    return str(exc).split("\n")[0][:100]


def _safe_file_name(file_name: str) -> str:
    """安全处理文件名：去除绝对路径，仅保留文件名。"""
    if not file_name:
        return "未知文件"
    if "\\" in file_name or "/" in file_name:
        from pathlib import Path
        return Path(file_name).name
    return file_name


def _safe_float(score, default: float = 0.0) -> float:
    """安全地将任意分数对象转换为 float。

    处理 HybridScore 对象、RetrievalScore 对象、int、float 等各种类型。
    任何异常都不会导致 chat 失败。
    """
    if isinstance(score, (int, float)):
        return float(score)
    # 尝试常见属性名
    for attr in ("hybrid_score", "rerank_score", "relevance_score", "score"):
        try:
            val = getattr(score, attr, None)
            if isinstance(val, (int, float)):
                return float(val)
        except Exception:
            continue
    # 最后尝试直接转换（可能触发 __float__）
    try:
        return float(score)
    except (TypeError, ValueError):
        return default


def _get_active_model_name() -> str:
    """获取当前实际生效的模型名称。"""
    try:
        from src.llm_client import get_active_llm_params
        params = get_active_llm_params()
        return params.get("model", "") or ""
    except Exception:
        return ""
