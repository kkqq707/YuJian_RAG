"""文档任务协调服务 (Phase 8)

协调文件上传、任务创建、后台索引、取消、重试等操作。

职责:
- 创建上传任务并加入队列
- 处理任务（作为 worker 的 task_processor）
- 管理文档状态与任务状态一致性
- 取消和重试
- 补偿逻辑
"""

from __future__ import annotations

import asyncio
import logging
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from sqlalchemy.orm import Session

from backend.app.config import get_settings
from backend.app.database import SessionLocal
from backend.app.models.document_task import DocumentTask
from backend.app.repositories.document_task_repository import (
    DocumentTaskRepository,
    TASK_STATUS_PENDING,
    TASK_STATUS_RUNNING,
    TASK_STATUS_COMPLETED,
    TASK_STATUS_FAILED,
    TASK_STATUS_CANCEL_REQUESTED,
    TASK_STATUS_CANCELLED,
    TASK_TERMINAL_STATES,
    TASK_TYPE_INDEX_DOCUMENT,
    TASK_TYPE_REBUILD_DOCUMENT,
    TASK_TYPE_REBUILD_KNOWLEDGE_BASE,
    TASK_TYPE_DELETE_DOCUMENT_VECTORS,
    ERR_TASK_INTERRUPTED,
    ERR_DOCUMENT_PARSE_TIMEOUT,
    ERR_DOCUMENT_INDEX_TIMEOUT,
    ERR_TASK_CANNOT_CANCEL,
    ERR_TASK_CANNOT_RETRY,
    ERR_ACTIVE_TASK_EXISTS,
    ERR_FILE_NOT_FOUND,
)
from backend.app.services.document_task_runtime import get_document_task_runtime
from backend.app.vector_store_runtime import (
    get_vector_store_runtime,
    VectorStoreBusyError,
)

logger = logging.getLogger(__name__)

# 文档索引状态常量（对应 knowledge_manager）
DOC_STATUS_PENDING = "pending"
DOC_STATUS_PROCESSING = "processing"
DOC_STATUS_COMPLETED = "completed"
DOC_STATUS_FAILED = "failed"


class DocumentTaskService:
    """文档任务协调服务。

    每个操作使用独立短 Session。
    """

    def __init__(self):
        self.settings = get_settings()
        self._ensure_src_path()

    @staticmethod
    def _ensure_src_path():
        project_root = get_settings().PROJECT_ROOT
        if str(project_root) not in sys.path:
            sys.path.insert(0, str(project_root))

    # ------------------------------------------------------------------
    # 创建任务
    # ------------------------------------------------------------------

    def create_index_task(
        self,
        document_id: str,
        task_type: str = TASK_TYPE_INDEX_DOCUMENT,
        created_by: str = "admin",
    ) -> DocumentTask:
        """创建文档索引任务并加入队列。

        Returns 创建的 DocumentTask。
        Raises ValueError 如果有冲突任务或队列满。
        """
        db = SessionLocal()
        try:
            repo = DocumentTaskRepository(db)
            task = repo.create_task(
                document_id=document_id,
                task_type=task_type,
                created_by=created_by,
            )
            db.commit()

            # 入队
            runtime = get_document_task_runtime()
            enqueued = runtime.enqueue_nowait(task.id)
            if not enqueued:
                db2 = SessionLocal()
                try:
                    repo2 = DocumentTaskRepository(db2)
                    task2 = repo2.get_task(task.id)
                    if task2:
                        repo2.update_task_status(
                            task2, TASK_STATUS_FAILED,
                            error_code="QUEUE_FULL",
                            error_message="任务队列已满，请稍后重试",
                        )
                    db2.commit()
                finally:
                    db2.close()
                raise ValueError("任务队列已满，请稍后重试")

            return task
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    def create_rebuild_task(self, created_by: str = "admin") -> DocumentTask:
        """创建知识库重建任务。"""
        db = SessionLocal()
        try:
            repo = DocumentTaskRepository(db)
            task = repo.create_task(
                document_id="__rebuild__",
                task_type=TASK_TYPE_REBUILD_KNOWLEDGE_BASE,
                created_by=created_by,
            )
            db.commit()

            # 入队
            runtime = get_document_task_runtime()
            enqueued = runtime.enqueue_nowait(task.id)
            if not enqueued:
                db2 = SessionLocal()
                try:
                    repo2 = DocumentTaskRepository(db2)
                    task2 = repo2.get_task(task.id)
                    if task2:
                        repo2.update_task_status(
                            task2, TASK_STATUS_FAILED,
                            error_code="QUEUE_FULL",
                            error_message="任务队列已满，请稍后重试",
                        )
                    db2.commit()
                finally:
                    db2.close()
                raise ValueError("任务队列已满，请稍后重试")

            return task
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    # ------------------------------------------------------------------
    # 任务处理 (worker 回调)
    # ------------------------------------------------------------------

    async def process_task(self, task_id: int) -> None:
        """处理单个文档任务。

        作为 worker 的 task_processor 回调。包含完整的任务生命周期。
        """
        db = SessionLocal()
        try:
            repo = DocumentTaskRepository(db)
            task = repo.get_task(task_id)

            if task is None:
                logger.warning("任务不存在: task_id=%d", task_id)
                return

            # 检查是否已取消
            if task.status in (TASK_STATUS_CANCELLED, TASK_STATUS_CANCEL_REQUESTED):
                logger.info("任务已取消，跳过: task_id=%d", task_id)
                return

            # 检查是否已终态
            if task.status in TASK_TERMINAL_STATES:
                logger.info("任务已完成，跳过: task_id=%d, status=%s", task_id, task.status)
                return

            # 标记运行中
            repo.update_task_status(
                task, TASK_STATUS_RUNNING,
                worker_id=get_document_task_runtime().worker_id,
                heartbeat_at=datetime.now(timezone.utc),
            )
            repo.update_task_progress(task, 5, "开始处理")
            db.commit()

        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

        t_start = time.perf_counter()
        runtime = get_document_task_runtime()

        try:
            if task.task_type == TASK_TYPE_INDEX_DOCUMENT:
                await self._process_index_task(task_id)
            elif task.task_type == TASK_TYPE_REBUILD_KNOWLEDGE_BASE:
                await self._process_rebuild_task(task_id)
            elif task.task_type == TASK_TYPE_REBUILD_DOCUMENT:
                await self._process_index_task(task_id)  # 复用同一逻辑
            elif task.task_type == TASK_TYPE_DELETE_DOCUMENT_VECTORS:
                await self._process_delete_task(task_id)
            else:
                self._fail_task(task_id, "UNKNOWN_TASK_TYPE",
                                f"未知任务类型: {task.task_type}")

        except asyncio.CancelledError:
            self._handle_cancellation(task_id)
            raise
        except Exception as e:
            error_msg = str(e).split("\n")[0][:500]
            logger.exception("任务处理异常: task_id=%d — %s", task_id, error_msg)
            self._fail_task(task_id, "TASK_EXECUTION_ERROR", error_msg)
        else:
            # 成功
            duration_ms = (time.perf_counter() - t_start) * 1000
            runtime.metrics.record_task_completed(duration_ms)

    async def _process_index_task(self, task_id: int):
        """处理文档索引任务。"""
        task = self._get_task(task_id)
        if not task or task.status == TASK_STATUS_CANCELLED:
            return

        document_id = task.document_id
        runtime = get_document_task_runtime()

        # ---- 检查取消 ----
        if not self._check_cancel(task_id):
            return

        # ---- 1. 源文件校验 (progress 10) ----
        self._update_progress(task_id, 10, "校验源文件")
        file_path = self._get_file_path(document_id)
        if file_path is None:
            self._fail_task(task_id, ERR_FILE_NOT_FOUND,
                            f"源文件不存在: {document_id}")
            return
        if not file_path.is_file():
            self._fail_task(task_id, ERR_FILE_NOT_FOUND,
                            f"文件在磁盘上不存在: {str(file_path)[:100]}")
            return

        # ---- 2. 更新文档状态为 processing ----
        self._update_doc_status(document_id, "processing")

        # ---- 3. 解析文档 (progress 25) ----
        if not self._check_cancel(task_id):
            return
        self._update_progress(task_id, 25, "解析文档")

        try:
            documents = await asyncio.wait_for(
                asyncio.get_event_loop().run_in_executor(
                    None,
                    self._load_document_sync,
                    file_path,
                ),
                timeout=self.settings.DOCUMENT_PARSE_TIMEOUT_SECONDS,
            )
        except asyncio.TimeoutError:
            runtime.metrics.record_parse_timeout()
            self._fail_task(task_id, ERR_DOCUMENT_PARSE_TIMEOUT,
                            f"文档解析超时 ({self.settings.DOCUMENT_PARSE_TIMEOUT_SECONDS}s)")
            return

        if not documents:
            self._fail_task(task_id, "EMPTY_DOCUMENT", "文档解析后无有效内容")
            return

        # 添加 metadata
        original_name = self._get_doc_field(document_id, "original_name") or "未知"
        tenant_id = self._get_doc_field(document_id, "tenant_id") or "default"
        for doc in documents:
            doc.metadata["upload_id"] = document_id
            doc.metadata["source_type"] = "upload"
            doc.metadata["original_name"] = original_name
            doc.metadata["knowledge_source"] = "upload"
            doc.metadata["tenant_id"] = tenant_id

        # ---- 4. 文本切分 (progress 40) ----
        if not self._check_cancel(task_id):
            self._cleanup_partial_vectors(document_id)
            return
        self._update_progress(task_id, 40, "文本切分")

        chunks = await asyncio.get_event_loop().run_in_executor(
            None, self._split_documents_sync, documents,
        )
        if not chunks:
            self._fail_task(task_id, "EMPTY_CHUNKS", "文档切分后无有效内容")
            return

        # ---- 5. 删除旧向量 ----
        self._remove_chunks_sync(document_id)

        # ---- 6. Embedding (progress 65) ----
        if not self._check_cancel(task_id):
            self._cleanup_partial_vectors(document_id)
            return
        self._update_progress(task_id, 65, "生成向量嵌入")

        try:
            await asyncio.wait_for(
                self._embed_and_write(chunks, document_id, original_name, tenant_id),
                timeout=self.settings.DOCUMENT_INDEX_TIMEOUT_SECONDS,
            )
        except asyncio.TimeoutError:
            runtime.metrics.record_index_timeout()
            self._cleanup_partial_vectors(document_id)
            self._fail_task(task_id, ERR_DOCUMENT_INDEX_TIMEOUT,
                            f"索引超时 ({self.settings.DOCUMENT_INDEX_TIMEOUT_SECONDS}s)")
            return

        if not self._check_cancel(task_id):
            self._cleanup_partial_vectors(document_id)
            return

        # ---- 7. 完成 (progress 100) ----
        self._update_progress(task_id, 100, "完成")
        self._complete_task(task_id, document_id, len(chunks))
        self._update_doc_status(document_id, "completed", chunk_count=len(chunks))

    async def _process_rebuild_task(self, task_id: int):
        """处理知识库重建任务。"""
        task = self._get_task(task_id)
        if not task:
            return

        if not self._check_cancel(task_id):
            return

        self._update_progress(task_id, 10, "准备重建")

        from src.index_manager import rebuild_all_indexes
        from src.knowledge_manager import init_database

        init_database()

        def log_progress(stage, detail, current, total):
            progress = 10 + int((current / max(total, 1)) * 85)
            self._update_progress(task_id, min(progress, 95), f"{stage}: {detail}")

        # 获取 Chroma 写锁
        vs_runtime = get_vector_store_runtime()
        try:
            await asyncio.wait_for(vs_runtime.write_lock.acquire(), timeout=30.0)
        except asyncio.TimeoutError:
            self._fail_task(task_id, "VECTOR_STORE_BUSY", "向量库繁忙，请稍后重试")
            return

        try:
            result = await asyncio.get_event_loop().run_in_executor(
                None, lambda: rebuild_all_indexes(progress_callback=log_progress)
            )

            if result["success"]:
                self._update_progress(task_id, 100, "重建完成")
                self._complete_task(task_id, "__rebuild__",
                                   result.get("total_chunks", 0))
            else:
                self._fail_task(task_id, "REBUILD_FAILED",
                               result.get("error", "重建失败"))
        finally:
            vs_runtime.write_lock.release()

    async def _process_delete_task(self, task_id: int):
        """处理文档向量删除任务。"""
        task = self._get_task(task_id)
        if not task:
            return

        from src.index_manager import remove_file_from_index

        vs_runtime = get_vector_store_runtime()
        try:
            await asyncio.wait_for(vs_runtime.write_lock.acquire(), timeout=30.0)
        except asyncio.TimeoutError:
            self._fail_task(task_id, "VECTOR_STORE_BUSY", "向量库繁忙")
            return

        try:
            result = await asyncio.get_event_loop().run_in_executor(
                None, lambda: remove_file_from_index(task.document_id)
            )
            if result["success"]:
                self._complete_task(task_id, task.document_id,
                                   result.get("deleted_count", 0))
            else:
                self._fail_task(task_id, "DELETE_FAILED",
                               result.get("error", "删除失败"))
        finally:
            vs_runtime.write_lock.release()

    # ------------------------------------------------------------------
    # 取消
    # ------------------------------------------------------------------

    def cancel_task(self, task_id: int) -> dict:
        """请求取消任务。"""
        db = SessionLocal()
        try:
            repo = DocumentTaskRepository(db)
            task = repo.get_task(task_id)

            if task is None:
                return {"success": False, "error_code": ERR_TASK_CANNOT_CANCEL,
                        "message": "任务不存在"}

            if task.status in TASK_TERMINAL_STATES:
                return {"success": False, "error_code": ERR_TASK_CANNOT_CANCEL,
                        "message": f"任务已处于终态 ({task.status})，无法取消"}

            if task.status == TASK_STATUS_CANCEL_REQUESTED:
                return {"success": True, "message": "任务已在取消中", "task_id": task_id,
                        "new_status": task.status}

            if task.status == TASK_STATUS_PENDING:
                # 直接取消
                repo.update_task_status(task, TASK_STATUS_CANCELLED)
                # 同步文档状态
                self._update_doc_status(task.document_id, DOC_STATUS_FAILED)
                db.commit()
                logger.info("pending 任务已取消: id=%d, doc=%s", task_id, task.document_id)
                return {"success": True, "message": "任务已取消", "task_id": task_id,
                        "new_status": TASK_STATUS_CANCELLED}

            elif task.status == TASK_STATUS_RUNNING:
                # 标记 cancel_requested，worker 在检查点处理
                repo.update_task_status(task, TASK_STATUS_CANCEL_REQUESTED)
                db.commit()
                logger.info("running 任务请求取消: id=%d, doc=%s", task_id, task.document_id)
                return {"success": True, "message": "正在取消任务...", "task_id": task_id,
                        "new_status": TASK_STATUS_CANCEL_REQUESTED}

        finally:
            db.close()

    # ------------------------------------------------------------------
    # 重试
    # ------------------------------------------------------------------

    def retry_task(self, task_id: int) -> DocumentTask:
        """重试失败或已取消的任务（创建新任务）。"""
        db = SessionLocal()
        try:
            repo = DocumentTaskRepository(db)
            task = repo.get_task(task_id)

            if task is None:
                raise ValueError(f"{ERR_TASK_CANNOT_RETRY}: 任务不存在")

            if task.status not in (TASK_STATUS_FAILED, TASK_STATUS_CANCELLED):
                raise ValueError(
                    f"{ERR_TASK_CANNOT_RETRY}: 只有 failed 或 cancelled 任务可以重试"
                )

            if task.retry_count >= self.settings.MAX_TASK_RETRY_COUNT:
                raise ValueError(
                    f"{ERR_TASK_CANNOT_RETRY}: 已达到最大重试次数 "
                    f"({self.settings.MAX_TASK_RETRY_COUNT})"
                )

            # 检查是否有活跃任务
            if repo.has_active_task_for_document(task.document_id):
                raise ValueError(
                    f"{ERR_ACTIVE_TASK_EXISTS}: 文档 {task.document_id} 已有活跃任务"
                )

            # 检查源文件
            file_path = self._get_file_path(task.document_id)
            if file_path is None or not file_path.is_file():
                raise ValueError(f"{ERR_FILE_NOT_FOUND}: 源文件不存在，无法重试")

            # 清理残留向量
            self._remove_chunks_sync(task.document_id)

            # 创建新任务
            new_task = repo.create_task(
                document_id=task.document_id,
                task_type=task.task_type,
                created_by="admin",
                original_task_id=task.id,
                retry_count=task.retry_count + 1,
            )
            db.commit()

            # 入队
            runtime = get_document_task_runtime()
            enqueued = runtime.enqueue_nowait(new_task.id)
            if not enqueued:
                raise ValueError("任务队列已满，请稍后重试")

            logger.info(
                "任务重试: old_id=%d → new_id=%d, doc=%s, retry=%d",
                task.id, new_task.id, task.document_id, new_task.retry_count,
            )
            return new_task

        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    # ------------------------------------------------------------------
    # 查询
    # ------------------------------------------------------------------

    def list_tasks(
        self,
        status: Optional[str] = None,
        task_type: Optional[str] = None,
        document_id: Optional[str] = None,
        offset: int = 0,
        limit: int = 50,
    ) -> tuple[list, int]:
        """分页查询任务列表。"""
        db = SessionLocal()
        try:
            repo = DocumentTaskRepository(db)
            tasks, total = repo.list_tasks(
                status=status, task_type=task_type,
                document_id=document_id, offset=offset, limit=limit,
            )
            # 转换为 dict 避免 Session 关闭后访问
            task_dicts = []
            for t in tasks:
                task_dicts.append({
                    "id": t.id,
                    "document_id": t.document_id,
                    "task_type": t.task_type,
                    "status": t.status,
                    "progress": t.progress,
                    "current_step": t.current_step,
                    "error_code": t.error_code,
                    "error_message": t.error_message,
                    "created_by": t.created_by,
                    "created_at": t.created_at.isoformat() if t.created_at else None,
                    "started_at": t.started_at.isoformat() if t.started_at else None,
                    "completed_at": t.completed_at.isoformat() if t.completed_at else None,
                    "cancelled_at": t.cancelled_at.isoformat() if t.cancelled_at else None,
                    "retry_count": t.retry_count,
                    "original_task_id": t.original_task_id,
                    "chunk_count": t.chunk_count,
                })
            return task_dicts, total
        finally:
            db.close()

    def get_task_detail(self, task_id: int) -> Optional[dict]:
        """获取任务详情。"""
        db = SessionLocal()
        try:
            repo = DocumentTaskRepository(db)
            task = repo.get_task(task_id)
            if task is None:
                return None
            return {
                "id": task.id,
                "document_id": task.document_id,
                "task_type": task.task_type,
                "status": task.status,
                "progress": task.progress,
                "current_step": task.current_step,
                "error_code": task.error_code,
                "error_message": task.error_message,
                "created_by": task.created_by,
                "created_at": task.created_at.isoformat() if task.created_at else None,
                "started_at": task.started_at.isoformat() if task.started_at else None,
                "completed_at": task.completed_at.isoformat() if task.completed_at else None,
                "cancelled_at": task.cancelled_at.isoformat() if task.cancelled_at else None,
                "retry_count": task.retry_count,
                "original_task_id": task.original_task_id,
                "chunk_count": task.chunk_count,
            }
        finally:
            db.close()

    def get_metrics(self) -> dict:
        """获取运行指标（仅管理员）。"""
        runtime = get_document_task_runtime()
        return runtime.metrics.snapshot()

    # ------------------------------------------------------------------
    # 启动恢复
    # ------------------------------------------------------------------

    def recover_on_startup(self) -> dict:
        """应用启动时恢复遗留任务。

        Returns 恢复统计信息。
        """
        result = {
            "interrupted_tasks": 0,
            "re_enqueued_pending": 0,
            "document_status_fixed": 0,
        }

        db = SessionLocal()
        try:
            repo = DocumentTaskRepository(db)

            # 1. 标记 running 任务为 interrupted
            interrupted = repo.mark_interrupted_tasks()
            result["interrupted_tasks"] = interrupted

            # 2. 修复文档状态
            running_tasks = repo.get_running_tasks()
            for task in running_tasks:
                # already marked as failed above
                self._update_doc_status(task.document_id, DOC_STATUS_FAILED)
                result["document_status_fixed"] += 1

            # 3. 重新入队 pending 任务
            pending_tasks = repo.get_pending_tasks(limit=20)
            runtime = get_document_task_runtime()
            for task in pending_tasks:
                if runtime.enqueue_nowait(task.id):
                    result["re_enqueued_pending"] += 1

            db.commit()
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

        if result["interrupted_tasks"] > 0 or result["re_enqueued_pending"] > 0:
            logger.info(
                "启动恢复完成: interrupted=%d, re_enqueued=%d, docs_fixed=%d",
                result["interrupted_tasks"],
                result["re_enqueued_pending"],
                result["document_status_fixed"],
            )

        return result

    # ------------------------------------------------------------------
    # 内部辅助
    # ------------------------------------------------------------------

    def _get_task(self, task_id: int) -> Optional[DocumentTask]:
        db = SessionLocal()
        try:
            return db.get(DocumentTask, task_id)
        finally:
            db.close()

    def _update_progress(self, task_id: int, progress: int, step: str):
        db = SessionLocal()
        try:
            task = db.get(DocumentTask, task_id)
            if task:
                repo = DocumentTaskRepository(db)
                repo.update_task_progress(task, progress, step)
                db.commit()
        except Exception as e:
            db.rollback()
            logger.warning("更新任务进度失败: task_id=%d — %s", task_id, str(e)[:200])
        finally:
            db.close()

    def _fail_task(self, task_id: int, error_code: str, error_message: str):
        db = SessionLocal()
        try:
            task = db.get(DocumentTask, task_id)
            if task:
                if task.status == TASK_STATUS_CANCELLED:
                    return  # 已被取消，不覆盖
                repo = DocumentTaskRepository(db)
                repo.update_task_status(
                    task, TASK_STATUS_FAILED,
                    error_code=error_code,
                    error_message=error_message[:500],
                )
                db.commit()
                # 同步文档状态
                self._update_doc_status(task.document_id, DOC_STATUS_FAILED,
                                       error_message=error_message)
            logger.warning("任务失败: id=%d, code=%s, msg=%s",
                          task_id, error_code, error_message[:200])
        except Exception as e:
            db.rollback()
            logger.error("更新任务失败状态时异常: %s", str(e)[:200])
        finally:
            db.close()

        runtime = get_document_task_runtime()
        runtime.metrics.record_task_failed()

    def _complete_task(self, task_id: int, document_id: str, chunk_count: int):
        db = SessionLocal()
        try:
            task = db.get(DocumentTask, task_id)
            if task:
                if task.status == TASK_STATUS_CANCELLED:
                    return
                repo = DocumentTaskRepository(db)
                repo.update_task_status(
                    task, TASK_STATUS_COMPLETED,
                    chunk_count=chunk_count,
                )
                db.commit()
        except Exception as e:
            db.rollback()
            logger.error("更新任务完成状态时异常: %s", str(e)[:200])
        finally:
            db.close()

    def _check_cancel(self, task_id: int) -> bool:
        """检查任务是否被请求取消。如果已取消，更新状态并清理。"""
        db = SessionLocal()
        try:
            task = db.get(DocumentTask, task_id)
            if task is None:
                return False
            if task.status == TASK_STATUS_CANCEL_REQUESTED:
                repo = DocumentTaskRepository(db)
                repo.update_task_status(task, TASK_STATUS_CANCELLED)
                db.commit()
                # 同步文档状态
                self._update_doc_status(task.document_id, DOC_STATUS_PENDING)
                return False
            return True
        finally:
            db.close()

    def _handle_cancellation(self, task_id: int):
        """处理 asyncio.CancelledError，标记任务为 cancelled。"""
        db = SessionLocal()
        try:
            task = db.get(DocumentTask, task_id)
            if task:
                repo = DocumentTaskRepository(db)
                repo.update_task_status(task, TASK_STATUS_CANCELLED,
                                       error_message="任务被取消")
                db.commit()
                self._cleanup_partial_vectors(task.document_id)
                self._update_doc_status(task.document_id, DOC_STATUS_PENDING)
            get_document_task_runtime().metrics.record_task_cancelled()
            logger.warning("任务已取消: id=%d, doc=%s", task_id,
                          task.document_id if task else "?")
        except Exception as e:
            db.rollback()
            logger.error("处理任务取消时异常: %s", str(e)[:200])
        finally:
            db.close()

    # ------------------------------------------------------------------
    # 文档/文件操作辅助
    # ------------------------------------------------------------------

    def _get_file_path(self, document_id: str) -> Optional[Path]:
        """获取文档的磁盘文件路径（安全验证）。"""
        from src.knowledge_manager import get_file_by_id
        from src.config import UPLOADS_DATA_DIR

        record = get_file_by_id(document_id)
        if not record:
            return None

        stored_name = record.get("stored_name", "")
        if not stored_name:
            return None

        file_path = UPLOADS_DATA_DIR / stored_name
        # 安全验证
        from backend.app.services.file_upload import validate_path_in_upload_dir
        if not validate_path_in_upload_dir(file_path, UPLOADS_DATA_DIR):
            logger.warning("文件路径校验失败: %s", str(file_path)[:200])
            return None

        return file_path

    def _get_doc_field(self, document_id: str, field: str) -> Optional[str]:
        from src.knowledge_manager import get_file_by_id
        record = get_file_by_id(document_id)
        if record:
            return record.get(field)
        return None

    @staticmethod
    def _load_document_sync(file_path: Path):
        """同步加载文档。"""
        from src.document_loader import load_single_file
        return load_single_file(file_path)

    @staticmethod
    def _split_documents_sync(documents):
        """同步切分文档。"""
        from src.text_splitter import split_documents, deduplicate_chunks
        chunks = split_documents(documents)
        return deduplicate_chunks(chunks)

    @staticmethod
    def _remove_chunks_sync(document_id: str) -> int:
        """同步删除文档的 Chroma 向量。"""
        from src.index_manager import _remove_chunks_by_upload_id
        return _remove_chunks_by_upload_id(document_id)

    async def _embed_and_write(
        self, chunks, document_id: str, original_name: str, tenant_id: str
    ):
        """执行 Embedding 并写入 Chroma（带写锁）。"""
        from src.embedding_model import get_embedding_model
        from langchain_chroma import Chroma
        from src.config import COLLECTION_NAME, CHROMA_DIR

        embedding = get_embedding_model()

        # 收集有效 chunks
        chunk_ids = []
        valid_chunks = []
        for chunk in chunks:
            cid = chunk.metadata.get("chunk_id")
            if not cid:
                continue
            chunk.metadata["upload_id"] = document_id
            chunk.metadata["source_type"] = "upload"
            chunk.metadata["original_name"] = original_name
            chunk.metadata["knowledge_source"] = "upload"
            chunk.metadata["tenant_id"] = tenant_id
            chunk_ids.append(cid)
            valid_chunks.append(chunk)

        if not valid_chunks:
            return

        # 获取写锁
        vs_runtime = get_vector_store_runtime()
        try:
            await asyncio.wait_for(vs_runtime.write_lock.acquire(), timeout=30.0)
        except asyncio.TimeoutError:
            raise VectorStoreBusyError("向量库繁忙")

        try:
            vectorstore = Chroma(
                collection_name=COLLECTION_NAME,
                embedding_function=embedding,
                persist_directory=str(CHROMA_DIR),
            )
            vectorstore.add_documents(documents=valid_chunks, ids=chunk_ids)
        finally:
            vs_runtime.write_lock.release()

    def _update_doc_status(self, document_id: str, status: str,
                          chunk_count: int = 0, error_message: str = ""):
        """更新 knowledge_metadata.db 中的文档状态。"""
        try:
            from src.knowledge_manager import update_index_status
            safe_error = error_message.split("\n")[0][:300] if error_message else None

            embedding_status = {
                DOC_STATUS_PENDING: "pending",
                DOC_STATUS_PROCESSING: "embedding",
                DOC_STATUS_COMPLETED: "completed",
                DOC_STATUS_FAILED: "failed",
            }.get(status, "pending")

            update_index_status(
                document_id, status,
                chunk_count=chunk_count,
                error_message=safe_error,
                embedding_status=embedding_status,
            )
        except Exception as e:
            logger.warning("更新文档状态失败: doc=%s, status=%s — %s",
                          document_id, status, str(e)[:200])

    def _cleanup_partial_vectors(self, document_id: str):
        """清理部分写入的向量（补偿逻辑）。"""
        try:
            self._remove_chunks_sync(document_id)
        except Exception as e:
            logger.warning("清理部分向量失败: doc=%s — %s",
                          document_id, str(e)[:200])
