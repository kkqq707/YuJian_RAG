"""RAG 适配层 — 将现有 RAGService 包装为后端可用服务

- 延迟初始化 RAGService（首次聊天请求时才加载 Embedding 和 Chroma）
- 单例缓存，避免每个请求重新加载
- ask_user() 不返回 sources / chunk_id / raw_distance / relevance_score / 绝对路径
- ask_admin() 返回经过裁剪的来源
- 向量库不存在时抛出明确业务错误
- 根据异常类型正确分类 HTTP 状态码（不把所有错误统一转换成 503）
"""

from __future__ import annotations

import logging
import sys
import traceback
import uuid
from functools import lru_cache
from pathlib import Path
from typing import Optional

from backend.app.config import get_settings
from backend.app.exceptions import (
    AppException,
    LLMServiceException,
    RAGUnavailableException,
    VectorStoreNotFoundException,
)

logger = logging.getLogger(__name__)


class UserChatResult:
    """普通用户问答结果 — 不含来源。"""

    __slots__ = (
        "answer", "refused", "refusal_reason", "model",
        "latency_seconds", "request_id",
    )

    def __init__(
        self,
        answer: str,
        refused: bool,
        refusal_reason: Optional[str],
        model: Optional[str],
        latency_seconds: float,
        request_id: str,
    ):
        self.answer = answer
        self.refused = refused
        self.refusal_reason = refusal_reason
        self.model = model
        self.latency_seconds = latency_seconds
        self.request_id = request_id


class AdminSource:
    """管理员可见的来源 — 经过裁剪，RAG 3.0 增强版。

    包含: 真实文件名、版本号、页码、内容预览
    """

    __slots__ = ("file_name", "version", "page", "content_preview")

    def __init__(
        self,
        file_name: str,
        version: Optional[str],
        page: Optional[int],
        content_preview: str,
    ):
        self.file_name = file_name
        self.version = version
        self.page = page
        self.content_preview = content_preview


class DebugInfo:
    """RAG 3.0 检索调试信息。"""

    __slots__ = ("query", "initial_results", "reranked_results",
                 "final_results", "refused", "refusal_reason", "config")

    def __init__(
        self,
        query: str,
        initial_results: list[dict],
        reranked_results: list[dict] | None,
        final_results: list[dict],
        refused: bool,
        refusal_reason: Optional[str],
        config: dict | None,
    ):
        self.query = query
        self.initial_results = initial_results
        self.reranked_results = reranked_results
        self.final_results = final_results
        self.refused = refused
        self.refusal_reason = refusal_reason
        self.config = config


class AdminChatResult(UserChatResult):
    """管理员问答结果 — 含经过裁剪的来源和可选调试信息。"""

    __slots__ = ("sources", "debug_info")

    def __init__(
        self,
        answer: str,
        refused: bool,
        refusal_reason: Optional[str],
        model: Optional[str],
        latency_seconds: float,
        request_id: str,
        sources: list[AdminSource],
        debug_info: Optional[dict] = None,
    ):
        super().__init__(
            answer=answer,
            refused=refused,
            refusal_reason=refusal_reason,
            model=model,
            latency_seconds=latency_seconds,
            request_id=request_id,
        )
        self.sources = sources
        self.debug_info = debug_info


# ---------------------------------------------------------------------------
# 内部 — 异常分类
# ---------------------------------------------------------------------------


def _classify_rag_error(exc: Exception, error_str: str) -> AppException:
    """根据异常类型和信息，返回对应状态码的 AppException。

    规则：
    - 向量库 / Chroma 错误 → 503 (RAGUnavailableException)
    - LLM 上游连接/超时/Key错误 → 分类为 502/504
    - Embedding 模型错误 → 503
    - TypeError (HybridScore 等类型错误) → 500 (内部缺陷)
    - 其他未知错误 → 500
    """
    error_lower = error_str.lower()

    # Chroma / 向量库相关 → 503
    chroma_keywords = ("chroma", "vector", "collection", "sqlite", "persist", "chromadb")
    if any(kw in error_lower for kw in chroma_keywords):
        return RAGUnavailableException(f"知识库检索服务暂时不可用: {error_str}")

    # Embedding 模型相关 → 503
    embedding_keywords = ("embedding", "bge", "sentence_transformers", "model_path")
    if any(kw in error_lower for kw in embedding_keywords):
        return RAGUnavailableException(f"向量化服务暂时不可用: {error_str}")

    # LLM 超时 → 504
    timeout_keywords = ("timeout", "timed out", "connect timeout", "read timeout")
    if any(kw in error_lower for kw in timeout_keywords):
        return AppException(
            code="CHAT_LLM_TIMEOUT",
            message="问答服务响应超时，请稍后重试",
            status_code=504,
        )

    # LLM 上游连接错误 → 502
    connection_keywords = ("connection", "connect error", "refused", "unreachable",
                          "dns", "resolve", "network")
    if any(kw in error_lower for kw in connection_keywords):
        return AppException(
            code="CHAT_LLM_CONNECTION_ERROR",
            message="大模型服务连接失败，请检查网络配置",
            status_code=502,
        )

    # LLM API Key / 认证 → 502 (上游认证问题)
    auth_keywords = ("api key", "apikey", "unauthorized", "invalid key", "auth",
                    "permission", "access denied")
    if any(kw in error_lower for kw in auth_keywords):
        return AppException(
            code="CHAT_LLM_AUTH_ERROR",
            message="大模型服务认证失败，请联系管理员检查 API 配置",
            status_code=502,
        )

    # LLM 限流 → 429
    rate_keywords = ("rate limit", "ratelimit", "too many requests", "quota")
    if any(kw in error_lower for kw in rate_keywords):
        return AppException(
            code="CHAT_LLM_RATE_LIMITED",
            message="大模型服务请求过于频繁，请稍后重试",
            status_code=429,
        )

    # LLM 响应格式异常 → 502
    llm_keywords = ("llm", "model", "response", "invoke", "generate", "openai",
                   "deepseek", "qwen", "dashscope", "langchain")
    if any(kw in error_lower for kw in llm_keywords):
        return LLMServiceException(f"大模型服务异常: {error_str}")

    # TypeError（类型错误，如 HybridScore round）→ 500 内部缺陷
    if isinstance(exc, TypeError):
        return AppException(
            code="RAG_INTERNAL_ERROR",
            message="问答处理异常，请联系管理员",
            status_code=500,
        )

    # 空知识库 → 200 正常但返回业务提示（不抛异常）
    empty_keywords = ("empty", "no result", "not found", "unknown")
    if any(kw in error_lower for kw in empty_keywords):
        return RAGUnavailableException(f"当前知识库暂无可检索内容: {error_str}")

    # 未分类错误 → 500
    return AppException(
        code="RAG_INTERNAL_ERROR",
        message=f"问答处理异常: {error_str}",
        status_code=500,
    )


# ---------------------------------------------------------------------------
# RAGAdapter — 单例
# ---------------------------------------------------------------------------


class RAGAdapter:
    """RAG 服务适配器。

    内部复用 src.rag_service.RAGService，提供面向 API 的安全接口。
    使用延迟初始化 + 单例模式，避免启动时加载重模型。
    """

    def __init__(self):
        self._rag_service = None
        self._initialized = False
        self._last_raw_result: dict = {}  # 保存最近一次 RAG 原始结果（供性能日志使用）

    # -------------------------------------------------------------------
    # 内部 — 延迟初始化
    # -------------------------------------------------------------------

    def _ensure_initialized(self):
        """确保 RAGService 已初始化（延迟加载）。"""
        if self._initialized:
            return

        settings = get_settings()
        project_root = settings.PROJECT_ROOT

        # 确保项目根在 sys.path 中
        if str(project_root) not in sys.path:
            sys.path.insert(0, str(project_root))

        try:
            from src.rag_service import RAGService
            from src.vector_store import vector_store_exists
        except ImportError as e:
            raise RAGUnavailableException(
                f"无法加载 RAG 核心模块，请确认项目结构完整: {e}"
            )

        if not vector_store_exists():
            raise VectorStoreNotFoundException()

        try:
            self._rag_service = RAGService()
            self._initialized = True
            logger.info("RAGService 初始化完成")
        except FileNotFoundError:
            raise VectorStoreNotFoundException()
        except Exception as e:
            raise RAGUnavailableException(f"RAG 服务初始化失败: {e}")

    # -------------------------------------------------------------------
    # 公开方法
    # -------------------------------------------------------------------

    def ask_user(self, question: str) -> UserChatResult:
        """普通用户问答 — 不返回任何来源或技术检索字段。

        使用普通用户 Prompt（隐藏来源、简洁回答），
        上下文仅包含文档内容，不含元数据标签。

        Parameters
        ----------
        question : str
            用户问题

        Returns
        -------
        UserChatResult
        """
        self._ensure_initialized()

        try:
            raw = self._rag_service.ask(question, user_mode=True)
            self._last_raw_result = raw
        except AppException:
            raise  # 业务异常直接透传（保持原始状态码）
        except TypeError as e:
            # 类型错误（如 round(HybridScore)）→ 内部代码缺陷，返回 500
            logger.error(
                "ask_user 类型错误 | question=%s | %s: %s\n%s",
                question[:100], type(e).__name__, str(e)[:200],
                traceback.format_exc(),
            )
            raise AppException(
                code="RAG_INTERNAL_ERROR",
                message="问答处理异常，请联系管理员",
                status_code=500,
            )
        except Exception as e:
            error_str = str(e).split("\n")[0][:200]
            logger.error(
                "ask_user 失败 | question=%s | %s: %s\n%s",
                question[:100], type(e).__name__, error_str,
                traceback.format_exc(),
            )
            raise _classify_rag_error(e, error_str)

        return UserChatResult(
            answer=raw.get("answer", ""),
            refused=raw.get("refused", False),
            refusal_reason=raw.get("refusal_reason"),
            model=raw.get("model"),
            latency_seconds=raw.get("latency_seconds", 0.0),
            request_id="",  # 由路由层填充
        )

    def ask_admin(
        self, question: str, debug: bool = False
    ) -> AdminChatResult:
        """管理员问答 — 返回经过裁剪的来源和可选调试信息。

        使用管理员 Prompt（允许引用来源、详细回答），
        上下文包含完整元数据标签。

        RAG 3.0 增强:
        - 来源包含: file_name, version, page, content_preview
        - 调试模式可查看完整检索链路

        Parameters
        ----------
        question : str
            用户问题
        debug : bool
            是否开启检索调试模式（返回完整检索链路）

        Returns
        -------
        AdminChatResult
        """
        self._ensure_initialized()

        try:
            raw = self._rag_service.ask(question, user_mode=False, debug=debug)
            self._last_raw_result = raw
        except AppException:
            raise  # 业务异常直接透传（保持原始状态码）
        except TypeError as e:
            # 类型错误（如 round(HybridScore)）→ 内部代码缺陷，返回 500
            logger.error(
                "ask_admin 类型错误 | question=%s | %s: %s\n%s",
                question[:100], type(e).__name__, str(e)[:200],
                traceback.format_exc(),
            )
            raise AppException(
                code="RAG_INTERNAL_ERROR",
                message="问答处理异常，请联系管理员",
                status_code=500,
            )
        except Exception as e:
            error_str = str(e).split("\n")[0][:200]
            logger.error(
                "ask_admin 失败 | question=%s | %s: %s\n%s",
                question[:100], type(e).__name__, error_str,
                traceback.format_exc(),
            )
            raise _classify_rag_error(e, error_str)

        # 构建安全来源列表（RAG 3.0 增强版）
        safe_sources: list[AdminSource] = []
        for src in raw.get("sources", []):
            file_name = src.get("file_name", "未知文件")
            if "\\" in file_name or "/" in file_name:
                file_name = Path(file_name).name

            content_preview = src.get("content_preview", "")
            page = src.get("page")
            version = src.get("version")

            safe_sources.append(AdminSource(
                file_name=file_name,
                version=version if version else None,
                page=page if isinstance(page, int) else None,
                content_preview=content_preview,
            ))

        return AdminChatResult(
            answer=raw.get("answer", ""),
            refused=raw.get("refused", False),
            refusal_reason=raw.get("refusal_reason"),
            model=raw.get("model"),
            latency_seconds=raw.get("latency_seconds", 0.0),
            request_id="",  # 由路由层填充
            sources=safe_sources,
            debug_info=raw.get("debug_info") if debug else None,
        )

    def health_check(self) -> dict:
        """RAG 组件健康检查 — 不初始化重模型。

        仅检查向量库是否存在，不加载 Embedding 或 LLM。

        Returns
        -------
        dict
            {"vector_store": "ok"|"not_found", "knowledge_chunks": int}
        """
        settings = get_settings()
        project_root = settings.PROJECT_ROOT

        if str(project_root) not in sys.path:
            sys.path.insert(0, str(project_root))

        try:
            from src.vector_store import vector_store_exists
        except ImportError:
            return {"vector_store": "error", "knowledge_chunks": 0}

        if not vector_store_exists():
            return {"vector_store": "not_found", "knowledge_chunks": 0}

        # 获取 chunk 数量（不加载 Embedding）
        try:
            from src.vector_store import get_chroma_client, get_or_create_collection
            from src.config import COLLECTION_NAME
            client = get_chroma_client()
            collection = get_or_create_collection()
            count = collection.count()
            logger.info(
                "[CHROMA HEALTH] connected=True collection=%s count=%s",
                COLLECTION_NAME, count,
            )
        except Exception as e:
            count = 0
            logger.warning(
                "[CHROMA HEALTH] connected=False error=%s",
                str(e).split("\n")[0][:150],
            )

        return {"vector_store": "ok", "knowledge_chunks": count}


# ---------------------------------------------------------------------------
# 单例
# ---------------------------------------------------------------------------


@lru_cache(maxsize=1)
def get_rag_adapter() -> RAGAdapter:
    """获取缓存的 RAGAdapter 单例。"""
    return RAGAdapter()
