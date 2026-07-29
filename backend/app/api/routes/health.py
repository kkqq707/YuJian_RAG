"""健康检查路由 — 生产级多维度检测 (Phase 10)

提供三个级别的健康检查:

1. Liveness  (/api/v1/health/live)  — 进程存活，轻量，Docker healthcheck 使用
2. Readiness (/api/v1/health/ready) — 所有组件就绪，负载均衡器使用
3. Health    (/api/v1/health)       — 综合健康（向后兼容）

原则:
- 健康检查不重新加载模型
- 健康检查不新建 Chroma Client
- 健康检查不执行真实 LLM 请求
- 健康检查不写数据库
- 健康检查耗时应低
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from sqlalchemy import text

from backend.app.config import get_settings
from backend.app.database import get_db_session

logger = logging.getLogger(__name__)

router = APIRouter(tags=["健康检查"])


# ---------------------------------------------------------------------------
# 内部检测函数
# ---------------------------------------------------------------------------

def _check_database() -> bool:
    """检测 SQLite 数据库连接 — SELECT 1。"""
    try:
        session = get_db_session()
        try:
            session.execute(text("SELECT 1"))
            return True
        finally:
            session.close()
    except Exception as e:
        logger.warning("健康检查: 数据库连接失败: %s", str(e).split("\n")[0][:150])
        return False


def _check_chroma() -> bool:
    """检测 Chroma 向量库连接 — 使用缓存的运行时，不新建 Client。"""
    try:
        import sys
        from backend.app.config import get_settings

        settings = get_settings()
        project_root = settings.PROJECT_ROOT
        if str(project_root) not in sys.path:
            sys.path.insert(0, str(project_root))

        from src.vector_store import get_chroma_client
        from src.config import COLLECTION_NAME

        client = get_chroma_client()

        try:
            collection = client.get_collection(COLLECTION_NAME)
            collection.count()  # 轻量操作，验证 collection 可达
            return True
        except Exception:
            # collection 不存在也视为就绪（首次部署）
            return True
    except Exception as e:
        logger.warning("健康检查: Chroma 连接失败: %s", str(e).split("\n")[0][:150])
        return False


def _check_embedding() -> bool:
    """检测 Embedding 运行时 — 确认模型已加载，不执行推理。"""
    try:
        from backend.app.services.inference_runtime import get_inference_runtime
        runtime = get_inference_runtime()
        if runtime is None:
            return False
        return runtime.embedding_available
    except Exception:
        return False


def _check_reranker() -> bool:
    """检测 Reranker 运行时 — 确认模型已加载，不执行推理。"""
    try:
        from backend.app.services.inference_runtime import get_inference_runtime
        runtime = get_inference_runtime()
        if runtime is None:
            return False
        return runtime.reranker_available
    except Exception:
        return False


def _check_document_task_runtime() -> bool:
    """检测文档后台任务运行时是否已启动。"""
    try:
        from backend.app.services.document_task_runtime import get_document_task_runtime
        runtime = get_document_task_runtime()
        if runtime is None:
            return False
        return runtime.is_running
    except Exception:
        return False


def _get_chroma_vector_count() -> Optional[int]:
    """获取 Chroma 向量数（只读，不写）。"""
    try:
        import sys
        from backend.app.config import get_settings

        settings = get_settings()
        project_root = settings.PROJECT_ROOT
        if str(project_root) not in sys.path:
            sys.path.insert(0, str(project_root))

        from src.vector_store import get_chroma_client
        from src.config import COLLECTION_NAME

        client = get_chroma_client()
        try:
            collection = client.get_collection(COLLECTION_NAME)
            return collection.count()
        except Exception:
            return 0
    except Exception:
        return None


# ---------------------------------------------------------------------------
# 端点
# ---------------------------------------------------------------------------

@router.get("/health/live")
async def liveness_check(request: Request):
    """Liveness 探针 — 仅验证进程存活和事件循环可响应。

    用于 Docker healthcheck，极其轻量:
    - 不查数据库
    - 不查 Chroma
    - 不加载模型
    - 不查外部 LLM

    Docker healthcheck 使用此端点，避免模型加载期间误杀容器。

    Returns:
        200: 进程正常
    """
    return JSONResponse(
        content={
            "status": "alive",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        },
        status_code=200,
    )


@router.get("/health/ready")
async def readiness_check(request: Request):
    """Readiness 探针 — 验证所有组件就绪。

    检查:
    - 数据库可达
    - Chroma runtime 已初始化
    - Embedding runtime 可用
    - Reranker runtime 可用
    - 文档任务 runtime 可用

    Returns:
        200: 所有组件就绪
        503: 部分组件未就绪
    """
    database_ok = _check_database()
    chroma_ok = _check_chroma()
    embedding_ok = _check_embedding()
    reranker_ok = _check_reranker()
    doc_task_ok = _check_document_task_runtime()

    components = {
        "database": database_ok,
        "chroma": chroma_ok,
        "embedding": embedding_ok,
        "reranker": reranker_ok,
        "document_task_runtime": doc_task_ok,
    }

    all_ready = all(components.values())

    return JSONResponse(
        content={
            "status": "ready" if all_ready else "not_ready",
            "components": components,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        },
        status_code=200 if all_ready else 503,
    )


@router.get("/health")
async def health_check(request: Request):
    """综合健康检查 — 向后兼容，多维度检测。

    Returns:
    - status: "healthy" | "unhealthy"
    - backend: bool  — 始终为 True（请求已到达此端点）
    - database: bool — SQLite 连接状态
    - rag: bool      — Chroma 向量库连接状态
    - timestamp: str — ISO 8601 检查时间

    HTTP 状态码:
    - 200: 所有组件正常
    - 503: 一个或多个组件异常
    """
    # Phase 9: 健康检查限流（高额度，300 req/min）
    from backend.app.client_ip import get_client_ip
    from backend.app.rate_limiter import check_rate_limit
    client_ip, _ = get_client_ip(request)
    check_rate_limit(client_ip, "health")

    database_ok = _check_database()
    rag_ok = _check_chroma()

    all_healthy = database_ok and rag_ok

    response_data = {
        "status": "healthy" if all_healthy else "unhealthy",
        "backend": True,
        "database": database_ok,
        "rag": rag_ok,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

    status_code = 200 if all_healthy else 503
    return JSONResponse(content=response_data, status_code=status_code)
