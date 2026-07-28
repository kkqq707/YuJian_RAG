"""文档任务后台运行时 (Phase 8)

进程内后台任务队列和 Worker 管理。

特性:
- 单进程内 asyncio.Queue 任务队列
- 可配置 worker 数量（默认 1）
- 有界队列（满时返回 503）
- 优雅关闭（停止接收新任务，等待当前任务完成）
- 启动恢复（标记 interrupted 任务，重新入队 pending 任务）
- 运行指标

前提:
- 单 Uvicorn Worker 部署
- 不依赖 Redis/Celery
"""

from __future__ import annotations

import asyncio
import logging
import threading
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional

from backend.app.config import get_settings

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# 运行指标
# ---------------------------------------------------------------------------


@dataclass
class DocumentTaskMetrics:
    """文档任务运行指标（进程内，重启归零）。"""

    _lock: threading.Lock = field(default_factory=threading.Lock)

    # 上传
    upload_active: int = 0
    upload_waiting: int = 0
    upload_total: int = 0
    upload_rejected_total: int = 0

    # 任务
    document_task_pending: int = 0
    document_task_running: int = 0
    document_task_completed_total: int = 0
    document_task_failed_total: int = 0
    document_task_cancelled_total: int = 0
    document_task_queue_full_total: int = 0
    document_parse_timeout_total: int = 0
    document_index_timeout_total: int = 0

    # 持续时间跟踪
    _task_durations: list[float] = field(default_factory=list)
    _max_durations: int = 100

    def record_upload(self):
        with self._lock:
            self.upload_total += 1

    def record_upload_rejected(self):
        with self._lock:
            self.upload_rejected_total += 1

    def record_task_completed(self, duration_ms: float):
        with self._lock:
            self.document_task_completed_total += 1
            self._task_durations.append(duration_ms)
            if len(self._task_durations) > self._max_durations:
                self._task_durations.pop(0)

    def record_task_failed(self):
        with self._lock:
            self.document_task_failed_total += 1

    def record_task_cancelled(self):
        with self._lock:
            self.document_task_cancelled_total += 1

    def record_queue_full(self):
        with self._lock:
            self.document_task_queue_full_total += 1

    def record_parse_timeout(self):
        with self._lock:
            self.document_parse_timeout_total += 1

    def record_index_timeout(self):
        with self._lock:
            self.document_index_timeout_total += 1

    @property
    def average_duration_ms(self) -> float:
        with self._lock:
            if not self._task_durations:
                return 0.0
            return sum(self._task_durations) / len(self._task_durations)

    def snapshot(self) -> dict:
        with self._lock:
            return {
                "upload_active": self.upload_active,
                "upload_waiting": self.upload_waiting,
                "upload_total": self.upload_total,
                "upload_rejected_total": self.upload_rejected_total,
                "document_task_pending": self.document_task_pending,
                "document_task_running": self.document_task_running,
                "document_task_completed_total": self.document_task_completed_total,
                "document_task_failed_total": self.document_task_failed_total,
                "document_task_cancelled_total": self.document_task_cancelled_total,
                "document_task_queue_full_total": self.document_task_queue_full_total,
                "document_parse_timeout_total": self.document_parse_timeout_total,
                "document_index_timeout_total": self.document_index_timeout_total,
                "document_task_average_duration_ms": round(self.average_duration_ms, 2),
            }


# ---------------------------------------------------------------------------
# 任务运行时
# ---------------------------------------------------------------------------


@dataclass
class DocumentTaskRuntime:
    """文档后台任务运行时。

    管理任务队列、worker 协程、并发控制、指标。
    """

    queue: asyncio.Queue = field(default_factory=lambda: asyncio.Queue())
    workers: list[asyncio.Task] = field(default_factory=list)
    shutdown_event: asyncio.Event = field(default_factory=asyncio.Event)
    worker_id: str = field(default_factory=lambda: f"worker-{uuid.uuid4().hex[:8]}")

    # 并发控制
    upload_semaphore: Optional[asyncio.Semaphore] = None
    task_semaphore: Optional[asyncio.Semaphore] = None

    # 指标
    metrics: DocumentTaskMetrics = field(default_factory=DocumentTaskMetrics)

    # 状态
    started: bool = False
    _task_processor: Optional[callable] = None

    async def start(
        self,
        task_processor: callable,
        num_workers: int = 1,
        queue_size: int = 20,
        max_concurrent_uploads: int = 2,
    ):
        """启动任务运行时。

        Parameters
        ----------
        task_processor : callable
            任务处理函数，签名: async (task_id: int) -> None
        num_workers : int
            worker 协程数量
        queue_size : int
            队列容量
        max_concurrent_uploads : int
            最大并发上传数
        """
        if self.started:
            logger.warning("任务运行时已启动，跳过")
            return

        self._task_processor = task_processor
        self.queue = asyncio.Queue(maxsize=queue_size)
        self.shutdown_event.clear()

        # 并发控制
        self.upload_semaphore = asyncio.Semaphore(max_concurrent_uploads)
        self.task_semaphore = asyncio.Semaphore(num_workers)

        if num_workers > 1:
            logger.warning(
                "DOCUMENT_TASK_WORKERS=%d (>1)，注意 Chroma 写锁和 CPU 竞争风险",
                num_workers,
            )

        # 启动 worker
        for i in range(num_workers):
            worker = asyncio.create_task(
                self._worker_loop(i),
                name=f"doc-task-worker-{i}",
            )
            self.workers.append(worker)

        self.started = True
        logger.info(
            "文档任务运行时已启动: workers=%d, queue_size=%d, upload_slots=%d",
            num_workers, queue_size, max_concurrent_uploads,
        )

    async def stop(self, graceful: bool = True, timeout: float = 30.0):
        """停止任务运行时。

        Parameters
        ----------
        graceful : bool
            True: 停止接收新任务，等待当前任务完成
            False: 立即取消所有 worker
        timeout : float
            优雅关闭的超时时间（秒）
        """
        if not self.started:
            return

        logger.info("文档任务运行时正在关闭 (graceful=%s)...", graceful)
        self.shutdown_event.set()

        if graceful:
            # 等待 worker 完成当前任务
            try:
                await asyncio.wait_for(
                    asyncio.gather(*self.workers, return_exceptions=True),
                    timeout=timeout,
                )
            except asyncio.TimeoutError:
                logger.warning("任务运行时关闭超时，强制取消 worker")
                for w in self.workers:
                    if not w.done():
                        w.cancel()
        else:
            for w in self.workers:
                if not w.done():
                    w.cancel()

        # 等待取消完成
        await asyncio.gather(*self.workers, return_exceptions=True)
        self.workers.clear()
        self.started = False
        logger.info("文档任务运行时已关闭")

    async def enqueue(self, task_id: int) -> bool:
        """将任务加入队列。

        Returns True 如果成功入队，False 如果队列满。
        """
        if self.shutdown_event.is_set():
            return False

        try:
            await asyncio.wait_for(
                self.queue.put(task_id),
                timeout=get_settings().DOCUMENT_TASK_QUEUE_TIMEOUT_SECONDS,
            )
            return True
        except asyncio.TimeoutError:
            self.metrics.record_queue_full()
            return False

    def enqueue_nowait(self, task_id: int) -> bool:
        """非阻塞入队（用于恢复场景）。"""
        if self.shutdown_event.is_set():
            return False
        try:
            self.queue.put_nowait(task_id)
            return True
        except asyncio.QueueFull:
            self.metrics.record_queue_full()
            return False

    async def _worker_loop(self, worker_index: int):
        """Worker 主循环 — 从队列获取任务并处理。"""
        logger.info("Worker-%d 已启动", worker_index)

        while not self.shutdown_event.is_set():
            try:
                # 等待任务（带超时以检查 shutdown）
                try:
                    task_id = await asyncio.wait_for(
                        self.queue.get(), timeout=1.0
                    )
                except asyncio.TimeoutError:
                    continue

                # 获取任务处理信号量
                async with self.task_semaphore:
                    if self.shutdown_event.is_set():
                        self.queue.task_done()
                        break

                    self.metrics.document_task_running += 1
                    t_start = time.perf_counter()

                    try:
                        await self._task_processor(task_id)
                    except Exception as e:
                        logger.exception(
                            "Worker-%d 任务处理异常: task_id=%d — %s",
                            worker_index, task_id, str(e)[:200],
                        )
                    finally:
                        duration_ms = (time.perf_counter() - t_start) * 1000
                        self.metrics.document_task_running -= 1
                        self.queue.task_done()

            except asyncio.CancelledError:
                logger.info("Worker-%d 被取消", worker_index)
                break
            except Exception as e:
                logger.error(
                    "Worker-%d 循环异常（不停止）: %s",
                    worker_index, str(e)[:200],
                )

        logger.info("Worker-%d 已停止", worker_index)

    def get_queue_length(self) -> int:
        """获取当前队列长度。"""
        return self.queue.qsize()

    def is_shutting_down(self) -> bool:
        return self.shutdown_event.is_set()


# ---------------------------------------------------------------------------
# 全局单例
# ---------------------------------------------------------------------------

_task_runtime: Optional[DocumentTaskRuntime] = None
_runtime_lock = threading.Lock()


def get_document_task_runtime() -> DocumentTaskRuntime:
    """获取全局 DocumentTaskRuntime 单例。"""
    global _task_runtime
    if _task_runtime is None:
        with _runtime_lock:
            if _task_runtime is None:
                _task_runtime = DocumentTaskRuntime()
    return _task_runtime


def reset_document_task_runtime():
    """重置运行时（仅测试使用）。"""
    global _task_runtime
    with _runtime_lock:
        _task_runtime = None
