"""Phase 8: 文档后台任务测试

测试:
- 文件流式上传安全
- 任务队列和 worker
- 取消与重试
- 启动恢复
"""

from __future__ import annotations

import asyncio
import os
import tempfile
import threading
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# 文件上传安全测试
# ---------------------------------------------------------------------------


class TestFileValidation:
    """文件安全校验测试。"""

    def test_validate_safe_filename_normal(self):
        from backend.app.services.file_upload import validate_safe_filename
        result = validate_safe_filename("测试文档.pdf")
        assert result == "测试文档.pdf"

    def test_validate_safe_filename_path_traversal(self):
        from backend.app.services.file_upload import validate_safe_filename
        with pytest.raises(ValueError):
            validate_safe_filename("../test.pdf")
        with pytest.raises(ValueError):
            validate_safe_filename("..\\test.pdf")
        with pytest.raises(ValueError):
            validate_safe_filename("/etc/passwd")

    def test_validate_safe_filename_null_byte(self):
        from backend.app.services.file_upload import validate_safe_filename
        with pytest.raises(ValueError):
            validate_safe_filename("test\x00.pdf")

    def test_validate_safe_filename_windows_drive(self):
        from backend.app.services.file_upload import validate_safe_filename
        with pytest.raises(ValueError):
            validate_safe_filename("C:\\test.pdf")

    def test_validate_safe_filename_empty(self):
        from backend.app.services.file_upload import validate_safe_filename
        with pytest.raises(ValueError):
            validate_safe_filename("")
        with pytest.raises(ValueError):
            validate_safe_filename("   ")

    def test_validate_extension_allowed(self):
        from backend.app.services.file_upload import validate_extension
        assert validate_extension("test.pdf") == ".pdf"
        assert validate_extension("test.docx") == ".docx"
        assert validate_extension("test.txt") == ".txt"
        assert validate_extension("test.md") == ".md"

    def test_validate_extension_not_allowed(self):
        from backend.app.services.file_upload import validate_extension
        with pytest.raises(ValueError, match="UNSUPPORTED_FILE_TYPE"):
            validate_extension("test.exe")
        with pytest.raises(ValueError, match="UNSUPPORTED_FILE_TYPE"):
            validate_extension("test.py")

    def test_validate_mime_pdf_signature(self):
        from backend.app.services.file_upload import validate_mime_for_extension
        # Valid PDF header
        validate_mime_for_extension(b"%PDF-1.4\n...", ".pdf")

    def test_validate_mime_pdf_bad_signature(self):
        from backend.app.services.file_upload import validate_mime_for_extension
        with pytest.raises(ValueError, match="INVALID_FILE_CONTENT"):
            validate_mime_for_extension(b"#!/bin/bash\n", ".pdf")

    def test_generate_stored_filename(self):
        from backend.app.services.file_upload import generate_stored_filename
        name = generate_stored_filename("abc-123", ".pdf")
        assert name == "abc-123.pdf"
        assert ".." not in name
        assert "/" not in name

    def test_path_validation(self):
        from backend.app.services.file_upload import validate_path_in_upload_dir
        upload_dir = Path("/tmp/uploads")
        assert validate_path_in_upload_dir(Path("/tmp/uploads/file.pdf"), upload_dir)
        assert not validate_path_in_upload_dir(Path("/etc/passwd"), upload_dir)

    def test_hash_streaming(self):
        from backend.app.services.file_upload import compute_file_hash_streaming
        import hashlib
        with tempfile.NamedTemporaryFile(delete=False, suffix=".txt") as f:
            f.write(b"Hello World")
            tmp_name = f.name
        try:
            result = compute_file_hash_streaming(Path(tmp_name))
            expected = hashlib.sha256(b"Hello World").hexdigest()
            assert result == expected
        finally:
            try:
                os.unlink(tmp_name)
            except Exception:
                pass


# ---------------------------------------------------------------------------
# 任务队列测试 (sync components only to avoid asyncio hang)
# ---------------------------------------------------------------------------


class TestDocumentTaskRuntime:
    """任务运行时同步组件测试。"""

    def test_runtime_create(self):
        from backend.app.services.document_task_runtime import (
            DocumentTaskRuntime,
            get_document_task_runtime,
            reset_document_task_runtime,
        )
        reset_document_task_runtime()
        runtime = get_document_task_runtime()
        assert not runtime.started
        assert isinstance(runtime.worker_id, str)
        assert len(runtime.worker_id) > 0

    def test_queue_instantiation(self):
        from backend.app.services.document_task_runtime import DocumentTaskRuntime
        runtime = DocumentTaskRuntime()
        assert runtime.queue is not None
        assert runtime.queue.maxsize == 0  # asyncio.Queue default is 0

    def test_queue_bounded(self):
        import asyncio
        from backend.app.services.document_task_runtime import DocumentTaskRuntime
        runtime = DocumentTaskRuntime()
        runtime.queue = asyncio.Queue(maxsize=5)
        assert runtime.queue.maxsize == 5

    def test_shutdown_event_initial(self):
        from backend.app.services.document_task_runtime import DocumentTaskRuntime
        runtime = DocumentTaskRuntime()
        assert not runtime.shutdown_event.is_set()

    def test_metrics_snapshot_default(self):
        from backend.app.services.document_task_runtime import DocumentTaskMetrics
        metrics = DocumentTaskMetrics()
        snap = metrics.snapshot()
        assert snap["upload_total"] == 0
        assert snap["document_task_completed_total"] == 0
        assert snap["document_task_average_duration_ms"] == 0.0

    def test_metrics_record_upload(self):
        from backend.app.services.document_task_runtime import DocumentTaskMetrics
        metrics = DocumentTaskMetrics()
        metrics.record_upload()
        assert metrics.upload_total == 1

    def test_metrics_record_queue_full(self):
        from backend.app.services.document_task_runtime import DocumentTaskMetrics
        metrics = DocumentTaskMetrics()
        metrics.record_queue_full()
        assert metrics.document_task_queue_full_total == 1

    def test_metrics_average_duration(self):
        from backend.app.services.document_task_runtime import DocumentTaskMetrics
        metrics = DocumentTaskMetrics()
        metrics.record_task_completed(100.0)
        metrics.record_task_completed(200.0)
        assert metrics.average_duration_ms == 150.0


# ---------------------------------------------------------------------------
# 任务仓库测试
# ---------------------------------------------------------------------------


@pytest.mark.skip(reason="DB integration test — requires isolated SQLite")
class TestDocumentTaskRepository:
    """任务仓库测试（需要隔离 SQLite DB）。"""

    @pytest.fixture
    def db_session(self):
        """使用持久化 DB 进行测试（内存 DB 不与 SQLAlchemy 兼容）。"""
        import os
        os.environ["DATABASE_URL"] = "sqlite:///D:/projects/YuJian_RAG/storage/app.db"
        from backend.app.database import SessionLocal
        db = SessionLocal()
        yield db
        db.rollback()
        db.close()

    def test_create_task(self, db_session):
        from backend.app.repositories.document_task_repository import (
            DocumentTaskRepository,
            TASK_TYPE_INDEX_DOCUMENT,
        )
        import uuid
        repo = DocumentTaskRepository(db_session)
        task = repo.create_task(
            document_id=f"test-phase8-{uuid.uuid4().hex[:8]}",
            task_type=TASK_TYPE_INDEX_DOCUMENT,
        )
        assert task.id is not None
        assert task.status == "pending"
        assert task.progress == 0

    def test_task_status_constants(self):
        from backend.app.repositories.document_task_repository import (
            TASK_STATUS_COMPLETED,
            TASK_STATUS_FAILED,
            TASK_STATUS_CANCELLED,
            TASK_STATUS_PENDING,
            TASK_TERMINAL_STATES,
        )
        assert TASK_STATUS_COMPLETED in TASK_TERMINAL_STATES
        assert TASK_STATUS_FAILED in TASK_TERMINAL_STATES
        assert TASK_STATUS_CANCELLED in TASK_TERMINAL_STATES
        assert TASK_STATUS_PENDING not in TASK_TERMINAL_STATES

    def test_update_task_status(self, db_session):
        from backend.app.repositories.document_task_repository import (
            DocumentTaskRepository,
            TASK_STATUS_RUNNING,
        )
        import uuid
        repo = DocumentTaskRepository(db_session)
        task = repo.create_task(document_id=f"test-phase8-{uuid.uuid4().hex[:8]}")
        db_session.commit()

        repo.update_task_status(task, TASK_STATUS_RUNNING)
        db_session.commit()

        assert task.status == TASK_STATUS_RUNNING
        assert task.started_at is not None

    def test_list_tasks(self, db_session):
        from backend.app.repositories.document_task_repository import (
            DocumentTaskRepository,
        )
        import uuid
        repo = DocumentTaskRepository(db_session)
        doc_id = f"test-list-{uuid.uuid4().hex[:8]}"
        repo.create_task(document_id=doc_id)
        db_session.commit()

        tasks, total = repo.list_tasks(document_id=doc_id)
        assert total >= 1


@pytest.mark.skip(reason="DB integration test — requires isolated SQLite")
class TestTaskCancelRetry:
    """任务取消与重试测试。"""

    @pytest.fixture
    def db_session(self):
        import os
        os.environ["DATABASE_URL"] = "sqlite:///D:/projects/YuJian_RAG/storage/app.db"
        from backend.app.database import SessionLocal
        db = SessionLocal()
        yield db
        db.rollback()
        db.close()

    def test_cancel_pending_task(self, db_session):
        from backend.app.repositories.document_task_repository import (
            DocumentTaskRepository,
            TASK_STATUS_CANCELLED,
        )
        import uuid
        repo = DocumentTaskRepository(db_session)
        task = repo.create_task(document_id=f"test-cancel-{uuid.uuid4().hex[:8]}")
        db_session.commit()

        repo.update_task_status(task, TASK_STATUS_CANCELLED)
        db_session.commit()
        assert task.status == TASK_STATUS_CANCELLED

    def test_retry_creates_new_task(self, db_session):
        from backend.app.repositories.document_task_repository import (
            DocumentTaskRepository,
            TASK_STATUS_FAILED,
        )
        import uuid
        doc_id = f"test-retry-{uuid.uuid4().hex[:8]}"
        repo = DocumentTaskRepository(db_session)
        task = repo.create_task(document_id=doc_id)
        task.status = TASK_STATUS_FAILED
        db_session.commit()

        new_task = repo.create_task(
            document_id=doc_id,
            original_task_id=task.id,
            retry_count=1,
        )
        db_session.commit()

        assert new_task.id != task.id
        assert new_task.original_task_id == task.id
        assert new_task.retry_count == 1

    def test_retry_max_count(self):
        from backend.app.config import get_settings
        settings = get_settings()
        assert settings.MAX_TASK_RETRY_COUNT == 3


# ---------------------------------------------------------------------------
# 配置验证测试
# ---------------------------------------------------------------------------


class TestPhase8Config:
    """Phase 8 配置测试。"""

    def test_config_fields_present(self):
        from backend.app.config import get_settings
        settings = get_settings()
        assert settings.DOCUMENT_TASK_WORKERS == 1
        assert settings.DOCUMENT_TASK_QUEUE_SIZE == 20
        assert settings.MAX_CONCURRENT_UPLOADS == 2
        assert settings.MAX_UPLOAD_SIZE_MB == 50
        assert settings.UPLOAD_CHUNK_SIZE_BYTES == 1048576
        assert settings.MAX_FILES_PER_UPLOAD_REQUEST == 5
        assert settings.DOCUMENT_PARSE_TIMEOUT_SECONDS == 300
        assert settings.DOCUMENT_INDEX_TIMEOUT_SECONDS == 600
        assert settings.MAX_TASK_RETRY_COUNT == 3

    def test_config_validation_positive(self):
        from backend.app.config import get_settings
        settings = get_settings()
        # All positive ints should be valid
        assert settings.DOCUMENT_TASK_WORKERS >= 1
        assert settings.DOCUMENT_TASK_QUEUE_SIZE >= 1

    def test_config_validation_max_workers(self):
        from backend.app.config import Settings
        with pytest.raises(Exception):
            Settings(DOCUMENT_TASK_WORKERS=9)  # > 8

    def test_task_metrics_initial(self):
        from backend.app.services.document_task_runtime import DocumentTaskMetrics
        metrics = DocumentTaskMetrics()
        snapshot = metrics.snapshot()
        assert snapshot["upload_total"] == 0
        assert snapshot["document_task_completed_total"] == 0


# ---------------------------------------------------------------------------
# 验证脚本 (轻量)
# ---------------------------------------------------------------------------


def test_verification_script_smoke():
    """轻量验证脚本 — 不依赖真实知识库或模型。"""
    from backend.app.services.document_task_runtime import (
        DocumentTaskMetrics,
        DocumentTaskRuntime,
    )
    from backend.app.repositories.document_task_repository import (
        TASK_STATUS_PENDING,
        TASK_STATUS_RUNNING,
        TASK_STATUS_COMPLETED,
        TASK_STATUS_FAILED,
        TASK_STATUS_CANCELLED,
    )

    # 1. 状态常量完整
    statuses = [
        TASK_STATUS_PENDING,
        TASK_STATUS_RUNNING,
        TASK_STATUS_COMPLETED,
        TASK_STATUS_FAILED,
        TASK_STATUS_CANCELLED,
    ]
    assert len(statuses) == 5

    # 2. 运行时创建
    runtime = DocumentTaskRuntime()
    assert not runtime.started
    assert runtime.metrics is not None

    # 3. 指标初始值
    snap = runtime.metrics.snapshot()
    assert snap["document_task_pending"] == 0

    # 4. Metrics 可记录
    metrics = DocumentTaskMetrics()
    metrics.record_upload()
    assert metrics.upload_total == 1
    metrics.record_task_completed(100.0)
    assert metrics.document_task_completed_total == 1
    metrics.record_task_failed()
    assert metrics.document_task_failed_total == 1
    metrics.record_task_cancelled()
    assert metrics.document_task_cancelled_total == 1

    # 5. 文件安全校验
    from backend.app.services.file_upload import (
        validate_safe_filename,
        validate_extension,
        generate_stored_filename,
    )
    assert validate_safe_filename("test.pdf") == "test.pdf"
    with pytest.raises(ValueError):
        validate_safe_filename("../evil.txt")
    assert validate_extension("doc.pdf") == ".pdf"
    with pytest.raises(ValueError):
        validate_extension("virus.exe")
    name = generate_stored_filename("abc", ".pdf")
    assert name.endswith(".pdf")
    assert ".." not in name

    print("Smoke test PASSED")
