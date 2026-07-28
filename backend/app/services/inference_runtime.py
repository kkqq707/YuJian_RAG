"""推理运行时资源管理 — 模型单例、并发控制、HTTP 客户端

本模块管理应用级推理资源:
- Embedding 模型单例
- Reranker 模型单例
- 推理 Semaphore (Embedding / Reranker 独立)
- 共享 ThreadPoolExecutor
- 共享 httpx.AsyncClient (外部 LLM)
- 用户级请求槽位
- 运行指标

所有资源通过 app.state.inference_runtime 访问。
业务模块不得各自维护全局模型实例。
"""

from __future__ import annotations

import asyncio
import functools
import logging
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from typing import Any, Optional

import httpx

from backend.app.config import get_settings

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# 统一推理异常
# ---------------------------------------------------------------------------


class InferenceQueueTimeoutError(Exception):
    """推理排队超时 — 对应 HTTP 503。"""

    def __init__(self, resource: str = "inference", waited_ms: float = 0):
        self.resource = resource
        self.waited_ms = waited_ms
        super().__init__(
            f"当前问答请求较多，请稍后重试 "
            f"(resource={resource}, waited={waited_ms:.0f}ms)"
        )


class InferenceExecutionTimeoutError(Exception):
    """推理执行超时 — 对应 HTTP 504。"""

    def __init__(self, resource: str = "inference", elapsed_ms: float = 0):
        self.resource = resource
        self.elapsed_ms = elapsed_ms
        super().__init__(
            f"本次处理超时，请缩短问题或稍后重试 "
            f"(resource={resource}, elapsed={elapsed_ms:.0f}ms)"
        )


class InferenceUnavailableError(Exception):
    """模型不可用 — 对应 HTTP 503。"""

    def __init__(self, resource: str = "inference", detail: str = ""):
        self.resource = resource
        self.detail = detail
        super().__init__(f"模型服务不可用 ({resource}): {detail}")


class UserRequestLimitError(Exception):
    """用户请求数超限 — 对应 HTTP 429。"""

    def __init__(self, user_id: str = ""):
        self.user_id = user_id
        super().__init__("当前已有回答正在生成，请稍候。")


# ---------------------------------------------------------------------------
# 轻量运行指标 (线程安全)
# ---------------------------------------------------------------------------


@dataclass
class InferenceMetrics:
    """进程内推理运行指标。

    所有字段使用 int/float，并发更新通过 threading.Lock 保护。
    进程重启后归零。
    """

    # 当前活跃/等待数
    embedding_active: int = 0
    embedding_waiting: int = 0
    reranker_active: int = 0
    reranker_waiting: int = 0
    rag_active: int = 0

    # 累计计数
    embedding_total: int = 0
    reranker_total: int = 0
    queue_timeout_total: int = 0
    execution_timeout_total: int = 0
    cancelled_total: int = 0
    error_total: int = 0

    _lock: threading.Lock = field(default_factory=threading.Lock)

    def snapshot(self) -> dict:
        """获取指标的线程安全快照。"""
        with self._lock:
            return {
                "embedding_active": self.embedding_active,
                "embedding_waiting": self.embedding_waiting,
                "reranker_active": self.reranker_active,
                "reranker_waiting": self.reranker_waiting,
                "rag_active": self.rag_active,
                "embedding_total": self.embedding_total,
                "reranker_total": self.reranker_total,
                "queue_timeout_total": self.queue_timeout_total,
                "execution_timeout_total": self.execution_timeout_total,
                "cancelled_total": self.cancelled_total,
                "error_total": self.error_total,
            }

    def inc_active(self, key: str) -> None:
        with self._lock:
            setattr(self, key, getattr(self, key) + 1)

    def dec_active(self, key: str) -> None:
        with self._lock:
            val = getattr(self, key)
            if val > 0:
                setattr(self, key, val - 1)

    def inc_waiting(self, key: str) -> None:
        with self._lock:
            setattr(self, key, getattr(self, key) + 1)

    def dec_waiting(self, key: str) -> None:
        with self._lock:
            val = getattr(self, key)
            if val > 0:
                setattr(self, key, val - 1)

    def inc_counter(self, key: str) -> None:
        with self._lock:
            setattr(self, key, getattr(self, key) + 1)


# ---------------------------------------------------------------------------
# 推理运行时
# ---------------------------------------------------------------------------


@dataclass
class InferenceRuntime:
    """应用级推理资源容器。

    在 FastAPI lifespan 启动阶段创建，存储在 app.state.inference_runtime。
    关闭阶段释放 ThreadPoolExecutor 和 httpx.AsyncClient。
    """

    # 模型
    embedding_model: Any = None
    reranker_model: Any = None

    # 并发控制
    embedding_semaphore: asyncio.Semaphore | None = None
    reranker_semaphore: asyncio.Semaphore | None = None

    # 共享线程池
    executor: ThreadPoolExecutor | None = None

    # 外部 LLM HTTP 客户端
    http_client: httpx.AsyncClient | None = None

    # 用户级请求槽位: user_id → 活跃计数
    _user_active_requests: dict[str, int] = field(default_factory=dict)
    _user_lock: threading.Lock = field(default_factory=threading.Lock)

    # 运行指标
    metrics: InferenceMetrics = field(default_factory=InferenceMetrics)

    # 初始化状态
    embedding_available: bool = False
    reranker_available: bool = False

    _closed: bool = False

    # -------------------------------------------------------------------
    # 用户级并发
    # -------------------------------------------------------------------

    def acquire_user_slot(self, user_id: str, max_per_user: int = 1) -> bool:
        """尝试为用户获取请求槽位。

        Returns True 如果成功获取，False 如果超限。
        """
        with self._user_lock:
            current = self._user_active_requests.get(user_id, 0)
            if current >= max_per_user:
                return False
            self._user_active_requests[user_id] = current + 1
            return True

    def release_user_slot(self, user_id: str) -> None:
        """释放用户请求槽位。"""
        with self._user_lock:
            current = self._user_active_requests.get(user_id, 0)
            if current <= 1:
                self._user_active_requests.pop(user_id, None)
            else:
                self._user_active_requests[user_id] = current - 1

    def get_user_active_count(self, user_id: str) -> int:
        """获取用户当前活跃请求数。"""
        with self._user_lock:
            return self._user_active_requests.get(user_id, 0)

    def get_active_user_count(self) -> int:
        """获取当前有活跃请求的用户数。"""
        with self._user_lock:
            return len(self._user_active_requests)

    # -------------------------------------------------------------------
    # 生命周期
    # -------------------------------------------------------------------

    async def close(self) -> None:
        """释放所有资源。幂等 — 多次调用安全。"""
        if self._closed:
            return
        self._closed = True

        logger.info("InferenceRuntime 开始关闭...")

        # 关闭 HTTP 客户端
        if self.http_client is not None:
            try:
                await self.http_client.aclose()
                logger.info("httpx.AsyncClient 已关闭")
            except Exception as e:
                logger.warning("关闭 httpx.AsyncClient 时出错: %s", e)

        # 关闭线程池
        if self.executor is not None:
            try:
                self.executor.shutdown(wait=True, cancel_futures=False)
                logger.info("ThreadPoolExecutor 已关闭")
            except Exception as e:
                logger.warning("关闭 ThreadPoolExecutor 时出错: %s", e)

        logger.info("InferenceRuntime 已关闭")

    # -------------------------------------------------------------------
    # Embedding 异步包装
    # -------------------------------------------------------------------

    async def encode_async(
        self,
        texts: list[str],
        request_id: str = "",
        user_id: str = "",
        *,
        embed_type: str = "document",  # "document" | "query"
    ) -> list[list[float]]:
        """异步执行 Embedding 推理，带并发控制和超时。

        Parameters
        ----------
        texts : list[str]
            待向量化的文本列表
        request_id : str
            请求 ID（用于日志）
        user_id : str
            用户 ID（用于日志）
        embed_type : str
            "document" (不加前缀) 或 "query" (加 BGE 前缀)

        Returns
        -------
        list[list[float]]
            向量列表

        Raises
        ------
        InferenceQueueTimeoutError, InferenceExecutionTimeoutError,
        InferenceUnavailableError
        """
        if not self.embedding_available or self.embedding_model is None:
            raise InferenceUnavailableError(resource="embedding", detail="模型未加载")

        if self.embedding_semaphore is None or self.executor is None:
            raise InferenceUnavailableError(resource="embedding", detail="运行时未初始化")

        settings = get_settings()
        queue_timeout = settings.INFERENCE_QUEUE_TIMEOUT_SECONDS
        task_timeout = settings.INFERENCE_TASK_TIMEOUT_SECONDS

        t_wait_start = time.perf_counter()

        # ---- 排队等待 ----
        self.metrics.inc_waiting("embedding_waiting")
        try:
            acquired = False
            try:
                async with asyncio.timeout(queue_timeout):
                    await self.embedding_semaphore.acquire()
                    acquired = True
            except TimeoutError:
                queue_wait_ms = (time.perf_counter() - t_wait_start) * 1000
                self.metrics.dec_waiting("embedding_waiting")
                self.metrics.inc_counter("queue_timeout_total")
                logger.warning(
                    "Embedding 排队超时 | request_id=%s user_id=%s "
                    "queue_wait_ms=%.0f batch_size=%d",
                    request_id, user_id, queue_wait_ms, len(texts),
                )
                raise InferenceQueueTimeoutError(
                    resource="embedding", waited_ms=queue_wait_ms,
                )
        finally:
            if not acquired:
                self.metrics.dec_waiting("embedding_waiting")

        queue_wait_ms = (time.perf_counter() - t_wait_start) * 1000

        # ---- 执行推理 ----
        self.metrics.inc_active("embedding_active")
        self.metrics.inc_counter("embedding_total")
        t_infer_start = time.perf_counter()

        try:
            # 根据类型选择 embedding 方法
            if embed_type == "query":
                from src.embedding_model import prepare_query
                processed = [prepare_query(t) for t in texts]
                fn = functools.partial(self.embedding_model.embed_query, processed)
                # embed_query 取单个字符串，需要循环
                loop = asyncio.get_event_loop()
                results = await asyncio.wait_for(
                    loop.run_in_executor(
                        self.executor,
                        lambda: [self.embedding_model.embed_query(t) for t in processed],
                    ),
                    timeout=task_timeout,
                )
            else:
                loop = asyncio.get_event_loop()
                results = await asyncio.wait_for(
                    loop.run_in_executor(
                        self.executor,
                        functools.partial(self.embedding_model.embed_documents, texts),
                    ),
                    timeout=task_timeout,
                )

            inference_ms = (time.perf_counter() - t_infer_start) * 1000
            logger.info(
                "Embedding 完成 | request_id=%s user_id=%s "
                "batch_size=%d queue_wait_ms=%.0f inference_ms=%.0f status=success",
                request_id, user_id, len(texts), queue_wait_ms, inference_ms,
            )
            return results

        except TimeoutError:
            inference_ms = (time.perf_counter() - t_infer_start) * 1000
            self.metrics.inc_counter("execution_timeout_total")
            logger.warning(
                "Embedding 执行超时 | request_id=%s user_id=%s "
                "batch_size=%d inference_ms=%.0f",
                request_id, user_id, len(texts), inference_ms,
            )
            raise InferenceExecutionTimeoutError(
                resource="embedding", elapsed_ms=inference_ms,
            )

        except asyncio.CancelledError:
            self.metrics.inc_counter("cancelled_total")
            logger.info(
                "Embedding 任务取消 | request_id=%s user_id=%s batch_size=%d",
                request_id, user_id, len(texts),
            )
            raise  # 必须继续抛出

        except Exception:
            self.metrics.inc_counter("error_total")
            logger.exception(
                "Embedding 推理异常 | request_id=%s user_id=%s batch_size=%d",
                request_id, user_id, len(texts),
            )
            raise

        finally:
            self.metrics.dec_active("embedding_active")
            self.embedding_semaphore.release()

    # -------------------------------------------------------------------
    # Reranker 异步包装
    # -------------------------------------------------------------------

    async def rerank_async(
        self,
        query: str,
        documents: list[Any],
        top_k: int = 5,
        request_id: str = "",
        user_id: str = "",
    ) -> list[tuple[Any, float]]:
        """异步执行 Reranker 推理，带并发控制和超时。

        Parameters
        ----------
        query : str
            查询文本
        documents : list[Document]
            候选文档列表
        top_k : int
            返回的 Top-N 数量
        request_id : str
        user_id : str

        Returns
        -------
        list[tuple[Document, float]]
            (Document, rerank_score) 列表

        Raises
        ------
        InferenceQueueTimeoutError, InferenceExecutionTimeoutError,
        InferenceUnavailableError
        """
        # 空候选直接返回
        if not documents:
            return []

        if not self.reranker_available or self.reranker_model is None:
            logger.info("Reranker 不可用，跳过重排序")
            return [(doc, 0.0) for doc in documents[:top_k]]

        if self.reranker_semaphore is None or self.executor is None:
            logger.info("Reranker 运行时未初始化，跳过重排序")
            return [(doc, 0.0) for doc in documents[:top_k]]

        settings = get_settings()
        queue_timeout = settings.INFERENCE_QUEUE_TIMEOUT_SECONDS
        task_timeout = settings.INFERENCE_TASK_TIMEOUT_SECONDS

        t_wait_start = time.perf_counter()

        # ---- 排队等待 ----
        self.metrics.inc_waiting("reranker_waiting")
        try:
            acquired = False
            try:
                async with asyncio.timeout(queue_timeout):
                    await self.reranker_semaphore.acquire()
                    acquired = True
            except TimeoutError:
                queue_wait_ms = (time.perf_counter() - t_wait_start) * 1000
                self.metrics.dec_waiting("reranker_waiting")
                self.metrics.inc_counter("queue_timeout_total")
                logger.warning(
                    "Reranker 排队超时 | request_id=%s user_id=%s "
                    "queue_wait_ms=%.0f candidate_count=%d",
                    request_id, user_id, queue_wait_ms, len(documents),
                )
                raise InferenceQueueTimeoutError(
                    resource="reranker", waited_ms=queue_wait_ms,
                )
        finally:
            if not acquired:
                self.metrics.dec_waiting("reranker_waiting")

        queue_wait_ms = (time.perf_counter() - t_wait_start) * 1000

        # ---- 执行推理 ----
        self.metrics.inc_active("reranker_active")
        self.metrics.inc_counter("reranker_total")
        t_infer_start = time.perf_counter()

        try:
            loop = asyncio.get_event_loop()
            result = await asyncio.wait_for(
                loop.run_in_executor(
                    self.executor,
                    functools.partial(
                        self.reranker_model.rerank,
                        query,
                        documents,
                        top_k=top_k,
                    ),
                ),
                timeout=task_timeout,
            )

            inference_ms = (time.perf_counter() - t_infer_start) * 1000
            logger.info(
                "Reranker 完成 | request_id=%s user_id=%s "
                "candidate_count=%d queue_wait_ms=%.0f reranker_ms=%.0f status=success",
                request_id, user_id, len(documents), queue_wait_ms, inference_ms,
            )
            return result

        except TimeoutError:
            inference_ms = (time.perf_counter() - t_infer_start) * 1000
            self.metrics.inc_counter("execution_timeout_total")
            logger.warning(
                "Reranker 执行超时 | request_id=%s user_id=%s "
                "candidate_count=%d inference_ms=%.0f",
                request_id, user_id, len(documents), inference_ms,
            )
            raise InferenceExecutionTimeoutError(
                resource="reranker", elapsed_ms=inference_ms,
            )

        except asyncio.CancelledError:
            self.metrics.inc_counter("cancelled_total")
            logger.info(
                "Reranker 任务取消 | request_id=%s user_id=%s candidate_count=%d",
                request_id, user_id, len(documents),
            )
            raise  # 必须继续抛出

        except Exception:
            self.metrics.inc_counter("error_total")
            logger.exception(
                "Reranker 推理异常 | request_id=%s user_id=%s candidate_count=%d",
                request_id, user_id, len(documents),
            )
            raise

        finally:
            self.metrics.dec_active("reranker_active")
            self.reranker_semaphore.release()


# ---------------------------------------------------------------------------
# 工厂函数 — 在 lifespan 中调用
# ---------------------------------------------------------------------------


def create_inference_runtime() -> InferenceRuntime:
    """创建并初始化推理运行时。

    在 FastAPI lifespan 启动阶段调用一次。
    加载模型、创建 Semaphore、Executor、HTTP Client。

    Returns
    -------
    InferenceRuntime
    """
    import sys
    from pathlib import Path

    settings = get_settings()
    project_root = settings.PROJECT_ROOT

    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))

    runtime = InferenceRuntime()

    logger.info("=" * 60)
    logger.info("  推理运行时初始化开始")
    logger.info("=" * 60)

    # 并发配置日志
    logger.info(
        "并发配置: embedding_max=%d reranker_max=%d thread_pool=%d "
        "queue_timeout=%ds task_timeout=%ds per_user=%d",
        settings.EMBEDDING_MAX_CONCURRENCY,
        settings.RERANKER_MAX_CONCURRENCY,
        settings.INFERENCE_THREAD_POOL_SIZE,
        settings.INFERENCE_QUEUE_TIMEOUT_SECONDS,
        settings.INFERENCE_TASK_TIMEOUT_SECONDS,
        settings.MAX_ACTIVE_RAG_REQUESTS_PER_USER,
    )

    # ---- 1. Embedding 模型 ----
    logger.info("Embedding:")
    try:
        from src.embedding_model import get_embedding_model, get_load_strategy_info
        strategy_info = get_load_strategy_info()
        logger.info("  model:     %s", strategy_info.get("model_name", ""))
        logger.info("  strategy:  %s", strategy_info.get("load_method", ""))

        emb_start = time.perf_counter()
        runtime.embedding_model = get_embedding_model()
        emb_elapsed = round(time.perf_counter() - emb_start, 2)
        runtime.embedding_available = True
        logger.info("  status:    [OK] loaded (%.2fs)", emb_elapsed)
        print(f"Embedding status: OK")
    except Exception as e:
        logger.warning("  status:    [WARN] %s", str(e).split("\n")[0][:150])
        print(f"Embedding status: FAILED")

    # ---- 2. Reranker 模型 ----
    logger.info("Reranker:")
    try:
        from src.reranker import get_reranker
        reranker = get_reranker()
        reranker.ensure_initialized()
        runtime.reranker_model = reranker
        runtime.reranker_available = reranker.is_available()
        status = "OK" if reranker.is_available() else "UNAVAILABLE"
        logger.info("  model:     %s", reranker.model_name)
        logger.info("  path:      %s", reranker.model_path or "<not found>")
        logger.info("  status:    [%s]", status)
        print(f"Reranker status: {status}")
    except Exception as e:
        logger.warning("  status:    [WARN] %s", str(e).split("\n")[0][:150])
        print(f"Reranker status: FAILED")

    # ---- 3. Semaphores ----
    runtime.embedding_semaphore = asyncio.Semaphore(
        settings.EMBEDDING_MAX_CONCURRENCY
    )
    runtime.reranker_semaphore = asyncio.Semaphore(
        settings.RERANKER_MAX_CONCURRENCY
    )
    logger.info(
        "Semaphores: embedding=%d, reranker=%d",
        settings.EMBEDDING_MAX_CONCURRENCY,
        settings.RERANKER_MAX_CONCURRENCY,
    )

    # ---- 4. ThreadPoolExecutor ----
    runtime.executor = ThreadPoolExecutor(
        max_workers=settings.INFERENCE_THREAD_POOL_SIZE,
        thread_name_prefix="inference-",
    )
    logger.info("ThreadPool: size=%d", settings.INFERENCE_THREAD_POOL_SIZE)

    # ---- 5. HTTP Client ----
    runtime.http_client = httpx.AsyncClient(
        timeout=httpx.Timeout(
            connect=settings.LLM_CONNECT_TIMEOUT_SECONDS,
            read=settings.LLM_READ_TIMEOUT_SECONDS,
            write=settings.LLM_WRITE_TIMEOUT_SECONDS,
            pool=settings.LLM_POOL_TIMEOUT_SECONDS,
        ),
        limits=httpx.Limits(
            max_connections=settings.LLM_MAX_CONNECTIONS,
            max_keepalive_connections=settings.LLM_MAX_KEEPALIVE_CONNECTIONS,
        ),
    )
    logger.info(
        "HTTP Client: connect=%ds read=%ds pool=%ds max_conn=%d keepalive=%d",
        settings.LLM_CONNECT_TIMEOUT_SECONDS,
        settings.LLM_READ_TIMEOUT_SECONDS,
        settings.LLM_POOL_TIMEOUT_SECONDS,
        settings.LLM_MAX_CONNECTIONS,
        settings.LLM_MAX_KEEPALIVE_CONNECTIONS,
    )

    logger.info("=" * 60)
    logger.info("  推理运行时初始化完成")
    logger.info("=" * 60)

    return runtime
