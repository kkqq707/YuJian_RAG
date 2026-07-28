"""Async RAG 适配器 — 使用 InferenceRuntime 进行并发控制的异步 RAG 服务

将原有同步 RAG 管道分解为异步阶段，每个阶段:
- Embedding: 通过 InferenceRuntime.encode_async() → Semaphore + Executor
- Reranker: 通过 InferenceRuntime.rerank_async() → Semaphore + Executor
- Chroma I/O: 通过 run_in_executor 移出事件循环
- LLM: 通过 run_in_executor 移出事件循环
- 用户级并发: 通过 InferenceRuntime.acquire_user_slot()

本模块是 Phase 6 的核心 — 将同步推理从事件循环中安全移出。
"""

from __future__ import annotations

import asyncio
import functools
import logging
import time
import uuid
from pathlib import Path
from typing import Any, Optional

from fastapi import Request

from backend.app.config import get_settings
from backend.app.exceptions import (
    AppException,
    LLMServiceException,
    RAGUnavailableException,
    VectorStoreNotFoundException,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Async RAG Adapter
# ---------------------------------------------------------------------------


class AsyncRAGAdapter:
    """异步 RAG 服务适配器。

    使用 InferenceRuntime 进行模型推理的并发控制。
    所有重 CPU/IO 操作通过 run_in_executor 移出事件循环。
    """

    def __init__(self, runtime=None):
        """初始化适配器。

        Parameters
        ----------
        runtime : InferenceRuntime, optional
            推理运行时。如果为 None，将在首次调用时从 app.state 获取。
        """
        self._runtime = runtime
        self._rag_service = None
        self._initialized = False

    def _get_runtime(self):
        """获取推理运行时。"""
        if self._runtime is None:
            raise RAGUnavailableException("推理运行时未初始化，请检查应用启动日志")
        return self._runtime

    def _ensure_sync_rag(self):
        """确保同步 RAGService 已初始化（在 executor 中调用）。"""
        if self._initialized:
            return

        import sys
        settings = get_settings()
        project_root = settings.PROJECT_ROOT

        if str(project_root) not in sys.path:
            sys.path.insert(0, str(project_root))

        from src.rag_service import RAGService
        from src.vector_store import vector_store_exists

        if not vector_store_exists():
            raise VectorStoreNotFoundException()

        self._rag_service = RAGService()
        self._initialized = True

    # -------------------------------------------------------------------
    # 异步 Embedding（供检索阶段使用）
    # -------------------------------------------------------------------

    async def _embed_query_async(
        self, query: str, request_id: str = "", user_id: str = ""
    ) -> list[float]:
        """异步向量化查询文本。"""
        runtime = self._get_runtime()
        results = await runtime.encode_async(
            [query],
            request_id=request_id,
            user_id=user_id,
            embed_type="query",
        )
        return results[0] if results else []

    async def _embed_documents_async(
        self, texts: list[str], request_id: str = "", user_id: str = ""
    ) -> list[list[float]]:
        """异步向量化文档列表。"""
        runtime = self._get_runtime()
        return await runtime.encode_async(
            texts,
            request_id=request_id,
            user_id=user_id,
            embed_type="document",
        )

    # -------------------------------------------------------------------
    # 异步 Chroma 查询
    # -------------------------------------------------------------------

    async def _chroma_query_async(
        self,
        query_embedding: list[float],
        n_results: int,
        filter_dict: dict | None = None,
    ) -> list[tuple[Any, float]]:
        """在 executor 中执行 Chroma 查询，避免阻塞事件循环。"""
        loop = asyncio.get_event_loop()
        runtime = self._get_runtime()
        return await loop.run_in_executor(
            runtime.executor,
            functools.partial(
                self._chroma_query_sync,
                query_embedding,
                n_results,
                filter_dict,
            ),
        )

    def _chroma_query_sync(
        self,
        query_embedding: list[float],
        n_results: int,
        filter_dict: dict | None = None,
    ) -> list[tuple[Any, float]]:
        """同步 Chroma 查询（在 executor 线程中运行）。"""
        import sys
        settings = get_settings()
        project_root = settings.PROJECT_ROOT
        if str(project_root) not in sys.path:
            sys.path.insert(0, str(project_root))

        from src.vector_store import get_chroma_client, distance_to_relevance
        from src.config import COLLECTION_NAME
        from langchain_core.documents import Document

        try:
            client = get_chroma_client()
            collection = client.get_collection(COLLECTION_NAME)
            actual_count = collection.count()
            if n_results > actual_count:
                n_results = actual_count
            if n_results <= 0:
                return []

            kwargs = {
                "query_embeddings": [query_embedding],
                "n_results": n_results,
                "include": ["documents", "metadatas", "distances"],
            }
            if filter_dict:
                kwargs["where"] = filter_dict

            raw_results = collection.query(**kwargs)

            results = []
            if raw_results["ids"] and raw_results["ids"][0]:
                for i, doc_id in enumerate(raw_results["ids"][0]):
                    doc_content = raw_results["documents"][0][i] if raw_results["documents"] else ""
                    doc_metadata = raw_results["metadatas"][0][i] if raw_results["metadatas"] else {}
                    doc_distance = raw_results["distances"][0][i] if raw_results["distances"] else 0.0
                    doc = Document(page_content=doc_content, metadata=doc_metadata)
                    results.append((doc, doc_distance))

            # 按距离升序排列
            results.sort(key=lambda x: x[1])
            return results
        except Exception as e:
            logger.exception("Chroma 查询失败")
            raise RAGUnavailableException(f"知识库检索服务暂时不可用: {str(e)[:200]}")

    # -------------------------------------------------------------------
    # 异步混合检索
    # -------------------------------------------------------------------

    async def _hybrid_retrieve_async(
        self,
        query: str,
        request_id: str = "",
        user_id: str = "",
    ) -> list[tuple[Any, Any]]:
        """异步混合检索：向量 + BM25。"""
        runtime = self._get_runtime()
        loop = asyncio.get_event_loop()

        import sys
        settings = get_settings()
        project_root = settings.PROJECT_ROOT
        if str(project_root) not in sys.path:
            sys.path.insert(0, str(project_root))

        from src.config import (
            TENANT_ID,
            HYBRID_FETCH_K,
            RAG_VECTOR_WEIGHT,
            COLLECTION_NAME,
        )
        from src.vector_store import get_chroma_client
        from src.hybrid_retriever import HybridRetriever, HybridScore
        from langchain_core.documents import Document

        filter_dict = {"tenant_id": TENANT_ID}

        # 获取 collection 实际数量
        try:
            client = get_chroma_client()
            collection = client.get_collection(COLLECTION_NAME)
            actual_count = collection.count()
        except Exception:
            actual_count = 0

        vector_k = max(HYBRID_FETCH_K * 2, 10)
        actual_top_k = min(vector_k, actual_count) if actual_count > 0 else vector_k

        if actual_top_k <= 0:
            return []

        # ---- 1. 向量 Embedding（受控异步） ----
        t_emb = time.perf_counter()
        query_embedding = await self._embed_query_async(query, request_id, user_id)
        embedding_ms = (time.perf_counter() - t_emb) * 1000

        # ---- 2. Chroma 向量查询（executor） ----
        t_vec = time.perf_counter()
        raw_vector_results = await self._chroma_query_async(
            query_embedding, actual_top_k, filter_dict,
        )
        vector_search_ms = (time.perf_counter() - t_vec) * 1000

        # 转换为带分数的结果
        from src.vector_store import distance_to_relevance, RetrievalScore
        vector_results = []
        for doc, distance in raw_vector_results:
            relevance = distance_to_relevance(distance)
            vector_results.append((
                doc,
                RetrievalScore(raw_distance=distance, relevance_score=relevance),
            ))

        # ---- 3. BM25 检索（executor） ----
        t_bm25 = time.perf_counter()
        try:
            from src.bm25_retriever import get_bm25_retriever
            bm25_results = await loop.run_in_executor(
                runtime.executor,
                functools.partial(
                    _bm25_search_sync, query, actual_top_k,
                ),
            )
        except Exception as e:
            logger.warning("BM25 检索失败: %s", str(e)[:100])
            bm25_results = []
        bm25_search_ms = (time.perf_counter() - t_bm25) * 1000

        # ---- 4. 分数融合（轻量计算，不阻塞） ----
        hybrid_retriever = HybridRetriever(
            vector_weight=RAG_VECTOR_WEIGHT,
            top_k=HYBRID_FETCH_K,
        )

        v_scores = hybrid_retriever._normalize_scores(
            [(doc, rs.relevance_score) for doc, rs in vector_results]
        )
        b_scores = hybrid_retriever._normalize_scores(bm25_results)

        doc_index: dict[str, dict] = {}
        for (doc, rs), norm_score in zip(vector_results, v_scores):
            chunk_id = doc.metadata.get("chunk_id", doc.page_content[:50])
            doc_index[chunk_id] = {
                "doc": doc, "v_score": norm_score, "b_score": 0.0,
                "v_raw": rs.relevance_score, "v_distance": rs.raw_distance,
            }

        for (doc, bm25_score), norm_score in zip(bm25_results, b_scores):
            chunk_id = doc.metadata.get("chunk_id", doc.page_content[:50])
            if chunk_id not in doc_index:
                doc_index[chunk_id] = {
                    "doc": doc, "v_score": 0.0, "b_score": norm_score,
                    "v_raw": 0.0, "v_distance": 0.0,
                }
            else:
                doc_index[chunk_id]["b_score"] = max(doc_index[chunk_id]["b_score"], norm_score)

        alpha = RAG_VECTOR_WEIGHT
        fused = []
        for info in doc_index.values():
            final_score = alpha * info["v_score"] + (1 - alpha) * info["b_score"]
            fused.append((
                info["doc"],
                HybridScore(
                    hybrid_score=round(final_score, 6),
                    vector_score=round(info["v_score"], 6),
                    bm25_score=round(info["b_score"], 6),
                    vector_raw=round(info["v_raw"], 6),
                    vector_distance=round(info["v_distance"], 6),
                    alpha=alpha,
                ),
            ))

        fused.sort(key=lambda x: x[1].hybrid_score, reverse=True)
        result = fused[:HYBRID_FETCH_K]

        logger.info(
            "Async Hybrid Search | request_id=%s user_id=%s "
            "embedding_ms=%.0f vector_search_ms=%.0f bm25_ms=%.0f result_count=%d",
            request_id, user_id, embedding_ms, vector_search_ms, bm25_search_ms, len(result),
        )

        return result

    # -------------------------------------------------------------------
    # 异步 Reranker
    # -------------------------------------------------------------------

    async def _rerank_async(
        self,
        query: str,
        documents: list[Any],
        top_k: int = 5,
        request_id: str = "",
        user_id: str = "",
    ) -> list[tuple[Any, float]]:
        """异步 Reranker 重排序。"""
        runtime = self._get_runtime()
        return await runtime.rerank_async(
            query, documents, top_k=top_k,
            request_id=request_id, user_id=user_id,
        )

    # -------------------------------------------------------------------
    # 异步 LLM
    # -------------------------------------------------------------------

    async def _generate_answer_async(
        self,
        question: str,
        context: str,
        user_mode: bool = True,
        request_id: str = "",
    ) -> tuple[str, str]:
        """在 executor 中执行 LLM 生成。"""
        loop = asyncio.get_event_loop()
        runtime = self._get_runtime()
        return await loop.run_in_executor(
            runtime.executor,
            functools.partial(
                self._generate_answer_sync,
                question, context, user_mode,
            ),
        )

    def _generate_answer_sync(
        self, question: str, context: str, user_mode: bool = True,
    ) -> tuple[str, str]:
        """同步 LLM 生成（在 executor 线程中运行）。"""
        import sys
        settings = get_settings()
        project_root = settings.PROJECT_ROOT
        if str(project_root) not in sys.path:
            sys.path.insert(0, str(project_root))

        from src.llm_client import get_llm, sanitize_llm_error
        from src.prompts import create_rag_prompt
        from langchain_core.messages import AIMessage

        llm = get_llm()
        prompt = create_rag_prompt(user_mode=user_mode)
        messages = prompt.invoke({"context": context, "question": question})

        try:
            response = llm.invoke(messages)
        except Exception as e:
            raise RuntimeError(sanitize_llm_error(e)) from e

        if isinstance(response, AIMessage):
            content = response.content
        elif hasattr(response, "content"):
            content = response.content
        else:
            content = str(response)

        if not content or not str(content).strip():
            raise RuntimeError("模型返回了空响应，请稍后重试")

        model_name = "unknown"
        try:
            if hasattr(llm, "model_name") and llm.model_name:
                model_name = llm.model_name
            elif hasattr(llm, "model") and llm.model:
                model_name = llm.model
        except Exception:
            pass

        return str(content).strip(), model_name or "unknown"

    # -------------------------------------------------------------------
    # 上下文构建（轻量操作）
    # -------------------------------------------------------------------

    async def _build_context_async(
        self,
        documents: list[tuple[Any, float]],
        user_mode: bool = True,
    ) -> tuple[str, list[tuple[Any, float]]]:
        """构建上下文字符串（轻量操作，不阻塞）。

        Returns (context_str, selected_documents)
        """
        import sys
        settings = get_settings()
        project_root = settings.PROJECT_ROOT
        if str(project_root) not in sys.path:
            sys.path.insert(0, str(project_root))

        from src.config import TOP_K

        # 去重
        valid = []
        seen: set[str] = set()
        for doc, score in documents:
            content_key = doc.page_content.strip()
            if content_key in seen:
                continue
            seen.add(content_key)
            valid.append((doc, score))

        if len(valid) > TOP_K:
            valid = valid[:TOP_K]

        # 构建上下文
        context = self._format_context_sync(valid, user_mode=user_mode)
        return context, valid

    def _format_context_sync(
        self, documents: list[tuple[Any, float]], user_mode: bool = True,
    ) -> str:
        """格式化上下文字符串。"""
        import sys
        settings = get_settings()
        project_root = settings.PROJECT_ROOT
        if str(project_root) not in sys.path:
            sys.path.insert(0, str(project_root))

        from src.prompts import format_context_documents
        from langchain_core.documents import Document

        if not documents:
            return "（无可用上下文）"

        docs = []
        scores = []
        for doc, rerank_score in documents:
            numeric_score = float(rerank_score) if isinstance(rerank_score, (int, float)) else 0.0
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

    # -------------------------------------------------------------------
    # 置信度评估
    # -------------------------------------------------------------------

    def _assess_sync(
        self, results: list[tuple[Any, Any]],
    ) -> dict:
        """同步置信度评估（轻量计算）。"""
        import sys
        settings = get_settings()
        project_root = settings.PROJECT_ROOT
        if str(project_root) not in sys.path:
            sys.path.insert(0, str(project_root))

        from src.retrieval_judge import is_retrieval_confident
        from src.vector_store import RetrievalScore

        converted = []
        for doc, score in results:
            if isinstance(score, RetrievalScore):
                converted.append((doc, score))
            else:
                numeric_score = float(score) if isinstance(score, (int, float)) else 0.0
                normalized = max(0.0, min(1.0, (numeric_score + 10) / 20))
                converted.append((
                    doc,
                    RetrievalScore(raw_distance=0.0, relevance_score=normalized),
                ))

        confident, reason = is_retrieval_confident(converted)
        return {"confident": confident, "reason": reason}

    # -------------------------------------------------------------------
    # 公开 async 方法
    # -------------------------------------------------------------------

    async def ask_user_async(
        self,
        question: str,
        request_id: str = "",
        user_id: str = "",
    ) -> dict:
        """异步普通用户问答（不返回来源）。

        Parameters
        ----------
        question : str
        request_id : str
        user_id : str

        Returns
        -------
        dict with keys: answer, refused, refusal_reason, model,
                        latency_seconds, embedding_ms, vector_search_ms,
                        reranker_ms, llm_ms, total_ms, sources
        """
        t0 = time.perf_counter()
        runtime = self._get_runtime()
        settings = get_settings()

        result = {
            "answer": "",
            "refused": False,
            "refusal_reason": None,
            "model": None,
            "latency_seconds": 0.0,
            "embedding_ms": 0.0,
            "vector_search_ms": 0.0,
            "reranker_ms": 0.0,
            "context_build_ms": 0.0,
            "llm_ms": 0.0,
            "total_ms": 0.0,
            "sources": [],
        }

        # 校验问题
        if not question or not question.strip():
            result["answer"] = "根据当前企业知识库，暂未找到相关信息。"
            result["refused"] = True
            result["refusal_reason"] = "问题为空"
            result["total_ms"] = (time.perf_counter() - t0) * 1000
            return result

        # ---- 1. Query Rewrite ----
        rewritten_question = question
        try:
            import sys
            project_root = settings.PROJECT_ROOT
            if str(project_root) not in sys.path:
                sys.path.insert(0, str(project_root))
            from src.query_rewriter import rewrite_query, is_query_rewrite_enabled
            if is_query_rewrite_enabled():
                rewritten_question = rewrite_query(question, use_llm=False)
        except Exception:
            pass

        # ---- 2. Hybrid 检索（含 Embedding） ----
        try:
            t_ret = time.perf_counter()
            retrieved = await self._hybrid_retrieve_async(
                rewritten_question, request_id, user_id,
            )
            retrieval_ms = (time.perf_counter() - t_ret) * 1000
        except Exception as e:
            logger.exception("Async 检索失败")
            result["answer"] = "根据当前企业知识库，暂未找到相关信息。"
            result["refused"] = True
            result["refusal_reason"] = f"检索失败: {str(e)[:100]}"
            result["total_ms"] = (time.perf_counter() - t0) * 1000
            return result

        result["retrieved_count"] = len(retrieved)

        # ---- 3. Reranker ----
        t_rerank = time.perf_counter()
        reranked = retrieved
        try:
            from src.config import RERANK_ENABLE, RERANK_TOP_K, RERANK_FETCH_K
            if RERANK_ENABLE and len(retrieved) > RERANK_TOP_K:
                docs = [doc for doc, _ in retrieved[:RERANK_FETCH_K]]
                reranked = await self._rerank_async(
                    rewritten_question, docs, top_k=RERANK_TOP_K,
                    request_id=request_id, user_id=user_id,
                )
        except Exception as e:
            logger.warning("Async Reranker 失败，使用原始结果: %s", str(e)[:100])
            reranked = retrieved
        result["reranker_ms"] = (time.perf_counter() - t_rerank) * 1000
        result["reranked_count"] = len(reranked)

        # ---- 4. 置信度评估 ----
        assessment = self._assess_sync(reranked)
        if not assessment["confident"]:
            result["answer"] = "根据当前企业知识库，暂未找到相关信息。"
            result["refused"] = True
            result["refusal_reason"] = assessment["reason"]
            result["total_ms"] = (time.perf_counter() - t0) * 1000
            return result

        # ---- 5. 上下文构建 ----
        t_ctx = time.perf_counter()
        context, selected_docs = await self._build_context_async(reranked, user_mode=True)
        result["context_build_ms"] = (time.perf_counter() - t_ctx) * 1000
        result["used_context_count"] = len(selected_docs)

        # ---- 6. LLM 生成 ----
        t_llm = time.perf_counter()
        try:
            answer, model_name = await self._generate_answer_async(
                question, context, user_mode=True, request_id=request_id,
            )
        except Exception as e:
            result["answer"] = "根据当前企业知识库，暂未找到相关信息。"
            result["refused"] = True
            result["refusal_reason"] = f"LLM 调用失败: {str(e)[:100]}"
            result["total_ms"] = (time.perf_counter() - t0) * 1000
            return result
        result["llm_ms"] = (time.perf_counter() - t_llm) * 1000

        result["answer"] = answer
        result["model"] = model_name
        result["refused"] = False

        # ---- 7. 构建来源 ----
        result["sources"] = self._build_sources_sync(selected_docs)

        result["total_ms"] = (time.perf_counter() - t0) * 1000
        result["latency_seconds"] = result["total_ms"] / 1000

        # 结构化阶段日志
        logger.info(
            "RAG Async | request_id=%s user_id=%s "
            "embedding_ms=%.0f vector_search_ms=%.0f reranker_ms=%.0f "
            "context_build_ms=%.0f llm_ms=%.0f total_ms=%.0f "
            "retrieved=%d reranked=%d final=%d status=%s",
            request_id, user_id,
            result.get("embedding_ms", 0),
            result.get("vector_search_ms", 0),
            result.get("reranker_ms", 0),
            result.get("context_build_ms", 0),
            result.get("llm_ms", 0),
            result.get("total_ms", 0),
            result.get("retrieved_count", 0),
            result.get("reranked_count", 0),
            result.get("used_context_count", 0),
            "success",
        )

        return result

    async def ask_admin_async(
        self,
        question: str,
        request_id: str = "",
        user_id: str = "",
        debug: bool = False,
    ) -> dict:
        """异步管理员问答（含来源）。

        流程与 ask_user_async 一致，但使用管理员 Prompt。
        """
        # 复用 user 流程，但使用 user_mode=False
        # 简化实现：使用同步 RAGService
        runtime = self._get_runtime()
        loop = asyncio.get_event_loop()

        t0 = time.perf_counter()
        try:
            result = await loop.run_in_executor(
                runtime.executor,
                functools.partial(
                    self._ask_admin_sync, question, debug,
                ),
            )
        except Exception as e:
            logger.exception("管理员问答失败")
            raise _classify_rag_error(e, str(e)[:200])

        result["total_ms"] = (time.perf_counter() - t0) * 1000
        result["latency_seconds"] = result["total_ms"] / 1000

        if "request_id" in result:
            result["request_id"] = request_id

        return result

    def _ask_admin_sync(self, question: str, debug: bool = False) -> dict:
        """同步管理员问答（在 executor 中运行）。"""
        self._ensure_sync_rag()
        raw = self._rag_service.ask(question, user_mode=False, debug=debug)
        return raw

    def _build_sources_sync(self, documents: list[tuple[Any, float]]) -> list[dict]:
        """构建安全来源列表。"""
        import sys
        settings = get_settings()
        project_root = settings.PROJECT_ROOT
        if str(project_root) not in sys.path:
            sys.path.insert(0, str(project_root))

        from src.config import MAX_SOURCE_PREVIEW_CHARS
        import re

        sources = []
        for rank, (doc, score) in enumerate(documents, start=1):
            file_name = doc.metadata.get("file_name", "未知文件")
            if "\\" in file_name or "/" in file_name:
                file_name = Path(file_name).name

            content = doc.page_content.strip()
            content_clean = re.sub(r"\s+", " ", content)
            preview = content_clean[:MAX_SOURCE_PREVIEW_CHARS]

            numeric_score = float(score) if isinstance(score, (int, float)) else 0.0

            sources.append({
                "rank": rank,
                "file_name": file_name,
                "version": doc.metadata.get("version", "v1"),
                "page": doc.metadata.get("page", 1),
                "chunk_id": doc.metadata.get("chunk_id", "未知"),
                "rerank_score": round(numeric_score, 4),
                "content_preview": preview,
            })

        return sources


# ---------------------------------------------------------------------------
# 辅助函数
# ---------------------------------------------------------------------------


def _bm25_search_sync(query: str, top_k: int) -> list:
    """同步 BM25 检索（在 executor 线程中运行）。"""
    from src.bm25_retriever import get_bm25_retriever
    bm25 = get_bm25_retriever()
    return bm25.search(query, top_k=top_k)


def _classify_rag_error(exc: Exception, error_str: str) -> AppException:
    """分类 RAG 错误。"""
    error_lower = error_str.lower()

    chroma_keywords = ("chroma", "vector", "collection", "sqlite", "persist", "chromadb")
    if any(kw in error_lower for kw in chroma_keywords):
        return RAGUnavailableException(f"知识库检索服务暂时不可用: {error_str}")

    embedding_keywords = ("embedding", "bge", "sentence_transformers", "model_path")
    if any(kw in error_lower for kw in embedding_keywords):
        return RAGUnavailableException(f"向量化服务暂时不可用: {error_str}")

    timeout_keywords = ("timeout", "timed out")
    if any(kw in error_lower for kw in timeout_keywords):
        return AppException(
            code="CHAT_LLM_TIMEOUT", message="问答服务响应超时，请稍后重试", status_code=504,
        )

    llm_keywords = ("llm", "model", "response", "invoke", "generate")
    if any(kw in error_lower for kw in llm_keywords):
        return LLMServiceException(f"大模型服务异常: {error_str}")

    return AppException(
        code="RAG_INTERNAL_ERROR",
        message=f"问答处理异常: {error_str}",
        status_code=500,
    )


# ---------------------------------------------------------------------------
# 单例
# ---------------------------------------------------------------------------


_async_adapter: Optional[AsyncRAGAdapter] = None


def get_async_rag_adapter() -> AsyncRAGAdapter:
    """获取缓存的 AsyncRAGAdapter 单例。"""
    global _async_adapter
    if _async_adapter is None:
        _async_adapter = AsyncRAGAdapter()
    return _async_adapter


def set_async_rag_runtime(runtime) -> None:
    """设置推理运行时（在 lifespan 中调用）。"""
    adapter = get_async_rag_adapter()
    adapter._runtime = runtime
