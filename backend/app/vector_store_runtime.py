"""Chroma Runtime 单例管理

Phase 7: 统一管理 PersistentClient、Collection、写锁、知识库级锁、运行指标。

要求：
- PersistentClient 进程内只创建一次
- Collection 进程内只 get/create 一次并缓存
- 查询操作允许并发，不持有写锁
- 写入/删除/重建索引等操作受应用级写锁保护
- 所有锁在异常、取消和超时时都必须释放
- 单 Uvicorn Worker 是该锁有效的前提之一
"""

from __future__ import annotations

import asyncio
import logging
import sys
import threading
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

from backend.app.config import get_settings

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# 异常
# ---------------------------------------------------------------------------


class VectorStoreBusyError(Exception):
    """知识库写操作繁忙（锁等待超时）。

    对应 HTTP 503 + VECTOR_STORE_BUSY。
    """

    def __init__(self, message: str = "知识库正在处理其他任务，请稍后重试"):
        self.message = message
        super().__init__(message)


class VectorStoreOperationError(Exception):
    """知识库操作失败。

    对应 HTTP 503 + VECTOR_STORE_OPERATION_FAILED。
    """

    def __init__(self, message: str = "知识库索引操作失败，请查看任务状态"):
        self.message = message
        super().__init__(message)


class DuplicateOperationError(Exception):
    """重复操作（如重建中再次请求重建）。

    对应 HTTP 409。
    """

    def __init__(self, message: str = "该操作正在进行中，请勿重复提交"):
        self.message = message
        super().__init__(message)


# ---------------------------------------------------------------------------
# 运行指标
# ---------------------------------------------------------------------------


@dataclass
class VectorStoreMetrics:
    """Chroma 运行指标（进程内，重启归零）。"""

    _lock: threading.Lock = field(default_factory=threading.Lock)

    # 活跃计数
    vector_query_active: int = 0
    vector_write_active: int = 0
    vector_write_waiting: int = 0

    # 累计计数
    vector_write_timeout_total: int = 0
    vector_write_error_total: int = 0
    vector_query_total: int = 0
    vector_write_total: int = 0

    # 数据库指标
    db_lock_retry_total: int = 0
    db_busy_error_total: int = 0
    db_transaction_ms: float = 0.0
    db_slow_transaction_total: int = 0

    # 事务计时上下文
    _transaction_start: float = 0.0

    def record_query(self):
        with self._lock:
            self.vector_query_total += 1

    def record_write(self):
        with self._lock:
            self.vector_write_total += 1

    def record_write_timeout(self):
        with self._lock:
            self.vector_write_timeout_total += 1

    def record_write_error(self):
        with self._lock:
            self.vector_write_error_total += 1

    def record_db_retry(self):
        with self._lock:
            self.db_lock_retry_total += 1

    def record_db_busy_error(self):
        with self._lock:
            self.db_busy_error_total += 1

    def start_transaction(self):
        self._transaction_start = time.perf_counter()

    def end_transaction(self, slow_threshold_ms: float = 1000.0):
        elapsed_ms = (time.perf_counter() - self._transaction_start) * 1000
        with self._lock:
            if elapsed_ms > slow_threshold_ms:
                self.db_slow_transaction_total += 1
            # 使用指数移动平均的简单实现
            if self.db_transaction_ms == 0.0:
                self.db_transaction_ms = elapsed_ms
            else:
                self.db_transaction_ms = self.db_transaction_ms * 0.9 + elapsed_ms * 0.1

    def snapshot(self) -> dict:
        with self._lock:
            return {
                "vector_query_active": self.vector_query_active,
                "vector_write_active": self.vector_write_active,
                "vector_write_waiting": self.vector_write_waiting,
                "vector_write_timeout_total": self.vector_write_timeout_total,
                "vector_write_error_total": self.vector_write_error_total,
                "vector_query_total": self.vector_query_total,
                "vector_write_total": self.vector_write_total,
                "db_lock_retry_total": self.db_lock_retry_total,
                "db_busy_error_total": self.db_busy_error_total,
                "db_transaction_ms": round(self.db_transaction_ms, 2),
                "db_slow_transaction_total": self.db_slow_transaction_total,
            }


# ---------------------------------------------------------------------------
# Vector Store Runtime
# ---------------------------------------------------------------------------


@dataclass
class VectorStoreRuntime:
    """Chroma 运行时单例。

    Attributes
    ----------
    client : chromadb.PersistentClient
        进程内唯一的 Chroma 客户端
    collection : chromadb.Collection
        进程内缓存的 Collection 引用
    collection_name : str
        Collection 名称
    write_lock : asyncio.Lock
        全局写操作锁
    knowledge_locks : dict[str, asyncio.Lock]
        知识库级锁（按 kb_id 索引）
    metrics : VectorStoreMetrics
        运行指标
    """

    client: Any = None
    collection: Any = None
    collection_name: str = ""
    write_lock: asyncio.Lock = field(default_factory=asyncio.Lock)
    knowledge_locks: dict[str, asyncio.Lock] = field(default_factory=dict)
    _locks_guard: asyncio.Lock = field(default_factory=asyncio.Lock)
    metrics: VectorStoreMetrics = field(default_factory=VectorStoreMetrics)
    _initialized: bool = False

    async def get_knowledge_lock(self, kb_id: str) -> asyncio.Lock:
        """获取知识库级锁（按需创建）。

        锁字典在无活跃任务后需要清理，避免无限增长。
        """
        async with self._locks_guard:
            if kb_id not in self.knowledge_locks:
                self.knowledge_locks[kb_id] = asyncio.Lock()
            return self.knowledge_locks[kb_id]

    async def cleanup_unused_locks(self):
        """清理无等待者的知识库锁。"""
        async with self._locks_guard:
            to_remove = []
            for kb_id, lock in self.knowledge_locks.items():
                if not lock.locked():
                    to_remove.append(kb_id)
            for kb_id in to_remove:
                del self.knowledge_locks[kb_id]

    def is_initialized(self) -> bool:
        return self._initialized

    def mark_initialized(self):
        self._initialized = True


# ---------------------------------------------------------------------------
# 全局单例
# ---------------------------------------------------------------------------

_vector_runtime: Optional[VectorStoreRuntime] = None
_runtime_lock = threading.Lock()


def get_vector_store_runtime() -> VectorStoreRuntime:
    """获取全局 VectorStoreRuntime 单例。"""
    global _vector_runtime
    if _vector_runtime is None:
        with _runtime_lock:
            if _vector_runtime is None:
                _vector_runtime = VectorStoreRuntime()
    return _vector_runtime


def reset_vector_store_runtime():
    """重置运行时（仅测试使用）。"""
    global _vector_runtime
    with _runtime_lock:
        _vector_runtime = None


# ---------------------------------------------------------------------------
# Chroma 客户端初始化（在 lifespan 中调用）
# ---------------------------------------------------------------------------


def init_chroma_client() -> VectorStoreRuntime:
    """初始化 Chroma PersistentClient 和 Collection。

    应在应用启动时调用一次（lifespan）。

    Returns
    -------
    VectorStoreRuntime
        初始化后的运行时

    Raises
    ------
    RuntimeError
        初始化失败
    """
    runtime = get_vector_store_runtime()

    if runtime.is_initialized():
        logger.info("Chroma 运行时已初始化，跳过")
        return runtime

    settings = get_settings()

    # 确保 src 在 path 中
    project_root = settings.PROJECT_ROOT
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))

    from src.config import CHROMA_DIR, COLLECTION_NAME

    try:
        import chromadb

        t0 = time.perf_counter()
        runtime.client = chromadb.PersistentClient(path=str(CHROMA_DIR))
        runtime.collection_name = COLLECTION_NAME

        # 获取或创建 collection
        try:
            runtime.collection = runtime.client.get_collection(COLLECTION_NAME)
            count = runtime.collection.count()
            logger.info(
                "Chroma collection '%s' 已加载，%d 个向量",
                COLLECTION_NAME, count,
            )
        except Exception:
            logger.info("Chroma collection '%s' 不存在，自动创建", COLLECTION_NAME)
            runtime.collection = runtime.client.create_collection(
                name=COLLECTION_NAME,
                metadata={"hnsw:space": "cosine"},
            )
            logger.info("Chroma collection '%s' 已创建", COLLECTION_NAME)

        runtime.mark_initialized()

        elapsed = round(time.perf_counter() - t0, 2)
        logger.info("Chroma 运行时初始化完成 (%.2fs)", elapsed)

        return runtime

    except Exception as e:
        logger.error("Chroma 运行时初始化失败: %s", str(e)[:200])
        raise RuntimeError(f"Chroma 初始化失败: {str(e)[:200]}") from e


# ---------------------------------------------------------------------------
# 便捷函数（供现有代码调用，避免大量重构）
# ---------------------------------------------------------------------------


def get_cached_chroma_client() -> Any:
    """获取缓存的 Chroma PersistentClient。

    如果运行时尚未初始化，回退到 src/vector_store.py 的 get_chroma_client()。
    """
    runtime = get_vector_store_runtime()
    if runtime.is_initialized() and runtime.client is not None:
        return runtime.client

    # 回退到旧单例（兼容过渡期）
    settings = get_settings()
    project_root = settings.PROJECT_ROOT
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))
    from src.vector_store import get_chroma_client
    return get_chroma_client()


def get_cached_collection() -> Any:
    """获取缓存的 Chroma Collection。

    如果运行时尚未初始化，回退到 src/vector_store.py 的 get_or_create_collection()。
    """
    runtime = get_vector_store_runtime()
    if runtime.is_initialized() and runtime.collection is not None:
        return runtime.collection

    # 回退到旧方法（兼容过渡期）
    settings = get_settings()
    project_root = settings.PROJECT_ROOT
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))
    from src.vector_store import get_or_create_collection
    return get_or_create_collection()
