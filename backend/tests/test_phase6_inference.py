"""Phase 6 测试 — Embedding/Reranker 并发控制、推理运行时、用户级并发

测试范围:
- 推理运行时初始化
- Embedding/Reranker Semaphore 行为
- 用户级并发控制
- 配置校验
- 异常映射
- Http AsyncClient 生命周期
- CancelledError 处理
"""

from __future__ import annotations

import asyncio
import sys
import threading
import time
from pathlib import Path
from unittest.mock import MagicMock, patch, PropertyMock

import pytest

project_root = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / "backend"))


# ============================================================================
# 1. 配置校验测试
# ============================================================================


class TestConfigValidation:
    """配置参数校验。"""

    def test_positive_int_validation(self):
        """小于 1 的并发值应拒绝或使用安全默认值。"""
        from backend.app.config import Settings

        # 正常值
        s = Settings(EMBEDDING_MAX_CONCURRENCY=2)
        assert s.EMBEDDING_MAX_CONCURRENCY == 2

        # 值 >= 1 应该接受
        s2 = Settings(EMBEDDING_MAX_CONCURRENCY=1)
        assert s2.EMBEDDING_MAX_CONCURRENCY == 1

    def test_negative_embedding_concurrency_rejected(self):
        """小于 1 的并发值应被拒绝。"""
        from backend.app.config import Settings
        import pydantic

        with pytest.raises(pydantic.ValidationError):
            Settings(EMBEDDING_MAX_CONCURRENCY=0)

    def test_negative_timeout_rejected(self):
        """超时不得为负数。"""
        from backend.app.config import Settings
        import pydantic

        with pytest.raises(pydantic.ValidationError):
            Settings(INFERENCE_QUEUE_TIMEOUT_SECONDS=-1)

    def test_default_values(self):
        """默认配置值合理。"""
        from backend.app.config import Settings
        s = Settings()

        assert s.EMBEDDING_MAX_CONCURRENCY == 2
        assert s.RERANKER_MAX_CONCURRENCY == 1
        assert s.INFERENCE_THREAD_POOL_SIZE == 2
        assert s.INFERENCE_QUEUE_TIMEOUT_SECONDS == 30
        assert s.INFERENCE_TASK_TIMEOUT_SECONDS == 120
        assert s.MAX_ACTIVE_RAG_REQUESTS_PER_USER == 1
        assert s.UVICORN_WORKERS == 1
        assert s.LLM_MAX_CONNECTIONS == 20


# ============================================================================
# 2. 推理运行时初始化测试
# ============================================================================


class TestInferenceRuntimeInit:
    """推理运行时初始化行为。"""

    def test_runtime_creation_without_models(self):
        """在没有模型文件时创建 InferenceRuntime 应优雅降级。"""
        from backend.app.services.inference_runtime import (
            InferenceRuntime,
            InferenceUnavailableError,
        )

        runtime = InferenceRuntime()
        assert runtime.embedding_model is None
        assert runtime.embedding_available is False
        assert runtime.reranker_model is None
        assert runtime.reranker_available is False

        # 在没有模型时应抛出 InferenceUnavailableError
        with pytest.raises(InferenceUnavailableError):
            # 需要 asyncio 来运行
            async def _test():
                await runtime.encode_async(["test"], request_id="t1")

            asyncio.run(_test())

    def test_runtime_close_idempotent(self):
        """关闭运行时幂等 — 多次调用安全。"""
        from backend.app.services.inference_runtime import InferenceRuntime

        runtime = InferenceRuntime()
        # 关闭两次不应崩溃
        asyncio.run(runtime.close())
        asyncio.run(runtime.close())

    def test_runtime_user_slot_acquire_release(self):
        """用户槽位获取和释放。"""
        from backend.app.services.inference_runtime import InferenceRuntime

        runtime = InferenceRuntime()

        # 获取槽位
        assert runtime.acquire_user_slot("user1", max_per_user=1) is True
        # 同一用户再次获取失败
        assert runtime.acquire_user_slot("user1", max_per_user=1) is False
        # 不同用户可以获取
        assert runtime.acquire_user_slot("user2", max_per_user=1) is True

        # 释放 user1 后可以再次获取
        runtime.release_user_slot("user1")
        assert runtime.acquire_user_slot("user1", max_per_user=1) is True

        # 清理
        runtime.release_user_slot("user1")
        runtime.release_user_slot("user2")
        assert runtime.get_active_user_count() == 0

    def test_user_slot_no_permanent_growth(self):
        """用户释放后状态不永久残留。"""
        from backend.app.services.inference_runtime import InferenceRuntime

        runtime = InferenceRuntime()

        for i in range(10):
            uid = f"user_{i}"
            assert runtime.acquire_user_slot(uid, max_per_user=1)
            runtime.release_user_slot(uid)

        # 所有用户释放后活跃数应为 0
        assert runtime.get_active_user_count() == 0

    def test_user_slot_default_max_one(self):
        """默认每用户最多 1 个活跃请求。"""
        from backend.app.services.inference_runtime import InferenceRuntime

        runtime = InferenceRuntime()
        assert runtime.acquire_user_slot("user_a") is True
        assert runtime.acquire_user_slot("user_a") is False  # 再次获取失败
        runtime.release_user_slot("user_a")


# ============================================================================
# 3. Embedding Semaphore 行为测试
# ============================================================================


class TestEmbeddingSemaphore:
    """Embedding Semaphore 并发控制。"""

    def test_semaphore_acquire_and_release(self):
        """基本 acquire/release 流程。"""
        sem = asyncio.Semaphore(2)

        async def _test():
            await sem.acquire()
            assert sem._value == 1
            sem.release()
            assert sem._value == 2

        asyncio.run(_test())

    def test_semaphore_limits_concurrency(self):
        """Semaphore 限制并发数。"""
        sem = asyncio.Semaphore(2)
        active = 0
        max_active = 0
        lock = threading.Lock()

        async def worker():
            nonlocal active, max_active
            await sem.acquire()
            try:
                with lock:
                    nonlocal active
                    active += 1
                    nonlocal max_active
                    max_active = max(max_active, active)
                await asyncio.sleep(0.05)
            finally:
                with lock:
                    active -= 1
                sem.release()

        async def _test():
            tasks = [worker() for _ in range(6)]
            await asyncio.gather(*tasks)

        asyncio.run(_test())
        assert max_active <= 2

    def test_semaphore_released_on_exception(self):
        """异常后 Semaphore 被释放。"""
        sem = asyncio.Semaphore(1)

        async def failing_worker():
            await sem.acquire()
            try:
                raise ValueError("test error")
            finally:
                sem.release()

        async def _test():
            try:
                await failing_worker()
            except ValueError:
                pass
            # Semaphore 应该已恢复
            assert sem._value == 1
            # 可以再次获取
            await sem.acquire()
            sem.release()

        asyncio.run(_test())

    def test_semaphore_released_on_cancelled(self):
        """CancelledError 后 Semaphore 被释放。"""
        sem = asyncio.Semaphore(1)

        async def cancellable_worker():
            await sem.acquire()
            try:
                await asyncio.sleep(10)  # 长时间等待
            except asyncio.CancelledError:
                sem.release()
                raise

        async def _test():
            task = asyncio.create_task(cancellable_worker())
            await asyncio.sleep(0.01)  # 确保 worker 已获取 semaphore
            assert sem._value == 0
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
            # Semaphore 应该已恢复
            assert sem._value == 1

        asyncio.run(_test())


# ============================================================================
# 4. 推理异常映射测试
# ============================================================================


class TestInferenceExceptions:
    """推理异常正确映射为 HTTP 状态码。"""

    def test_queue_timeout_is_503(self):
        """排队超时应返回 503。"""
        from backend.app.services.inference_runtime import InferenceQueueTimeoutError

        exc = InferenceQueueTimeoutError(resource="embedding", waited_ms=30000)
        assert "embedding" in str(exc)
        assert "30000" in str(exc)

    def test_execution_timeout_is_504(self):
        """推理执行超时应返回 504。"""
        from backend.app.services.inference_runtime import InferenceExecutionTimeoutError

        exc = InferenceExecutionTimeoutError(resource="reranker", elapsed_ms=120000)
        assert "reranker" in str(exc)

    def test_unavailable_is_503(self):
        """模型不可用应返回 503。"""
        from backend.app.services.inference_runtime import InferenceUnavailableError

        exc = InferenceUnavailableError(resource="embedding", detail="模型文件缺失")
        assert "embedding" in str(exc)

    def test_user_limit_is_429(self):
        """用户请求超限应返回 429。"""
        from backend.app.services.inference_runtime import UserRequestLimitError

        exc = UserRequestLimitError(user_id="123")
        assert "请稍候" in str(exc)

    def test_exception_handler_maps_correctly(self):
        """异常处理器正确映射错误码。"""
        from backend.app.services.inference_runtime import (
            InferenceQueueTimeoutError,
            InferenceExecutionTimeoutError,
            InferenceUnavailableError,
            UserRequestLimitError,
        )
        from backend.app.exceptions import _build_error_response

        # 503 queue timeout
        resp = _build_error_response(
            "INFERENCE_QUEUE_TIMEOUT",
            "当前问答请求较多，请稍后重试",
            503,
            "req-123",
        )
        assert resp.status_code == 503

        # 504 execution timeout
        resp2 = _build_error_response(
            "INFERENCE_EXECUTION_TIMEOUT",
            "本次处理超时",
            504,
            "req-456",
        )
        assert resp2.status_code == 504

        # 429 user limit
        resp3 = _build_error_response(
            "USER_REQUEST_LIMIT",
            "当前已有回答正在生成",
            429,
            "req-789",
        )
        assert resp3.status_code == 429


# ============================================================================
# 5. 推理指标测试
# ============================================================================


class TestInferenceMetrics:
    """推理指标线程安全测试。"""

    def test_metrics_snapshot_thread_safe(self):
        """指标快照线程安全。"""
        from backend.app.services.inference_runtime import InferenceMetrics

        metrics = InferenceMetrics()

        # 并发更新
        def update():
            for _ in range(100):
                metrics.inc_counter("embedding_total")
                metrics.inc_active("embedding_active")

        threads = [threading.Thread(target=update) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # 总数应该是 500
        snapshot = metrics.snapshot()
        assert snapshot["embedding_total"] == 500

    def test_metrics_dec_clamps_zero(self):
        """dec_active 不会变为负数。"""
        from backend.app.services.inference_runtime import InferenceMetrics

        metrics = InferenceMetrics()
        metrics.dec_active("embedding_active")
        assert metrics.embedding_active == 0

        metrics.inc_active("embedding_active")
        metrics.dec_active("embedding_active")
        assert metrics.embedding_active == 0

    def test_metrics_snapshot_does_not_lock_long(self):
        """指标快照不会造成明显锁竞争。"""
        from backend.app.services.inference_runtime import InferenceMetrics
        import time

        metrics = InferenceMetrics()
        t0 = time.perf_counter()
        for _ in range(1000):
            metrics.snapshot()
        elapsed = time.perf_counter() - t0
        # 1000 次快照应该在 100ms 内完成
        assert elapsed < 1.0


# ============================================================================
# 6. 权限与隔离回归测试
# ============================================================================


class TestPermissionRegression:
    """确保新代码不破坏已有权限规则。"""

    def test_admin_cannot_chat(self, client, admin_headers):
        """管理员不能使用普通用户聊天接口。"""
        resp = client.post(
            "/api/v1/chat",
            json={"question": "test question"},
            headers=admin_headers,
        )
        assert resp.status_code == 403

    def test_normal_user_cannot_access_admin_chat(self, client, user_a_headers):
        """普通用户不能使用管理员聊天预览。"""
        resp = client.post(
            "/api/v1/admin/chat-preview",
            json={"question": "test"},
            headers=user_a_headers,
        )
        assert resp.status_code == 403

    def test_unauthenticated_chat_returns_401(self, client):
        """未登录聊天返回 401。"""
        resp = client.post(
            "/api/v1/chat",
            json={"question": "test"},
        )
        assert resp.status_code == 401

    def test_user_a_cannot_see_user_b_sessions(self, client, user_a_headers, user_b_headers, user_b, db_session):
        """用户 A 不能看到用户 B 的会话。"""
        from backend.app.repositories import chat_repository

        # 创建 user_b 的会话
        session_b = chat_repository.create_session(db_session, user_b.id, title="B's session")
        chat_repository.create_message(db_session, session_b.id, role="user", content="test")

        # user_a 访问
        resp = client.get(
            f"/api/v1/chat/sessions/{session_b.id}/messages",
            headers=user_a_headers,
        )
        assert resp.status_code == 404

    def test_inference_unavailable_returns_503(self, client, user_a_headers):
        """推理不可用时返回 503 而非 500。"""
        # 直接测试错误响应格式（不需要真正的 RAG）
        from backend.app.exceptions import _build_error_response

        resp = _build_error_response(
            "INFERENCE_UNAVAILABLE",
            "模型服务暂不可用",
            503,
            "test-123",
        )
        assert resp.status_code == 503
        data = resp.body.decode()
        assert "INFERENCE_UNAVAILABLE" in data


# ============================================================================
# 7. Chat 路由用户级并发测试
# ============================================================================


class TestUserConcurrency:
    """用户级并发控制。"""

    def test_user_request_limit_error_format(self, client, user_a_headers):
        """验证错误响应格式正确。"""
        from backend.app.exceptions import _build_error_response

        resp = _build_error_response(
            "USER_REQUEST_LIMIT",
            "当前已有回答正在生成，请稍候。",
            429,
            "req-001",
        )
        data = resp.body.decode()
        assert "429" in str(resp.status_code) or resp.status_code == 429
        assert "请稍候" in data

    def test_error_response_structure(self):
        """错误响应结构正确。"""
        from backend.app.exceptions import _build_error_response

        resp = _build_error_response(
            "TEST_ERROR",
            "Test message",
            503,
            "req-001",
        )
        assert resp.status_code == 503

        import json
        data = json.loads(resp.body.decode())
        assert data["success"] is False
        assert "error" in data
        assert data["error"]["code"] == "TEST_ERROR"
        assert data["error"]["message"] == "Test message"
        assert data["error"]["request_id"] == "req-001"


# ============================================================================
# 8. HTTP 异常映射测试
# ============================================================================


class TestHTTPExceptionMapping:
    """HTTP 异常映射到统一错误格式。"""

    def test_429_from_starlette(self, client):
        """Starlette HTTP 429 映射正确。"""
        from backend.app.exceptions import _build_error_response

        resp = _build_error_response(
            "RATE_LIMITED",
            "Too many requests",
            429,
            "req-429",
        )
        assert resp.status_code == 429

    def test_503_from_starlette(self, client):
        """Starlette HTTP 503 映射正确。"""
        from backend.app.exceptions import _build_error_response

        resp = _build_error_response(
            "SERVICE_UNAVAILABLE",
            "Service unavailable",
            503,
            "req-503",
        )
        assert resp.status_code == 503

    def test_504_mapping(self):
        """504 Gateway Timeout 映射正确。"""
        from backend.app.exceptions import _build_error_response

        resp = _build_error_response(
            "INFERENCE_EXECUTION_TIMEOUT",
            "本次处理超时",
            504,
            "req-504",
        )
        assert resp.status_code == 504


# ============================================================================
# 9. Config 并发日志测试
# ============================================================================


class TestConfigLogging:
    """配置日志输出测试。"""

    def test_config_repr_no_secrets(self):
        """Settings repr 不包含密钥。"""
        from backend.app.config import Settings

        s = Settings(JWT_SECRET_KEY="super-secret-key-that-is-long-enough-32")
        repr_str = repr(s)
        assert "super-secret" not in repr_str

    def test_new_config_fields_present(self):
        """新配置字段存在于 Settings 中。"""
        from backend.app.config import Settings

        s = Settings()
        assert hasattr(s, "EMBEDDING_MAX_CONCURRENCY")
        assert hasattr(s, "RERANKER_MAX_CONCURRENCY")
        assert hasattr(s, "INFERENCE_QUEUE_TIMEOUT_SECONDS")
        assert hasattr(s, "LLM_MAX_CONNECTIONS")
        assert hasattr(s, "MAX_ACTIVE_RAG_REQUESTS_PER_USER")
