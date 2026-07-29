"""健康检查路由 — 生产级多维度检测

检测维度:
1. FastAPI 服务状态（始终为 True，因为请求已到达）
2. SQLite 数据库连接
3. Chroma 向量库连接
4. RAG 初始化状态
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from sqlalchemy import text

from backend.app.config import get_settings
from backend.app.database import get_db_session
from backend.app.schemas.system import HealthResponse

logger = logging.getLogger(__name__)

router = APIRouter(tags=["健康检查"])


def _check_database() -> bool:
    """检测 SQLite 数据库连接是否正常。"""
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


def _ensure_chroma_collection() -> bool:
    """确保 Chroma collection 存在，不存在则自动创建。

    启动时 Chroma collection 可能尚未创建（首次部署或无文档上传），
    此函数确保 collection 存在以支持健康检查。

    健康检查逻辑（Chroma v0.6.x 兼容）:
      1. Chroma client 连接成功
      2. target collection 存在（不存在则自动创建）
      3. collection.count() >= 0
    以上全部满足 → healthy。不要求向量库必须有数据。

    Returns
    -------
    bool
        True 如果 collection 存在或创建成功
    """
    try:
        import sys
        from pathlib import Path

        settings = get_settings()
        project_root = settings.PROJECT_ROOT
        if str(project_root) not in sys.path:
            sys.path.insert(0, str(project_root))

        from src.vector_store import get_chroma_client
        from src.config import COLLECTION_NAME

        client = get_chroma_client()

        # 尝试获取或创建 collection
        try:
            collection = client.get_collection(COLLECTION_NAME)
            logger.debug("健康检查: Chroma collection '%s' 已存在", COLLECTION_NAME)
        except Exception:
            # collection 不存在 → 自动创建空 collection
            logger.info(
                "健康检查: Chroma collection '%s' 不存在，自动创建",
                COLLECTION_NAME,
            )
            try:
                client.create_collection(COLLECTION_NAME)
                logger.info(
                    "健康检查: Chroma collection '%s' 已自动创建",
                    COLLECTION_NAME,
                )
                collection = client.get_collection(COLLECTION_NAME)
            except Exception as create_err:
                logger.warning(
                    "健康检查: Chroma collection 自动创建失败: %s",
                    str(create_err).split("\n")[0][:150],
                )
                logger.warning(
                    "[CHROMA HEALTH] connected=False error=%s",
                    str(create_err).split("\n")[0][:150],
                )
                return False

        # 验证 collection 可操作（count >= 0 即视为 healthy）
        count = collection.count()
        logger.info(
            "[CHROMA HEALTH] connected=True collection=%s count=%s",
            COLLECTION_NAME, count,
        )
        return True

    except Exception as e:
        logger.warning("健康检查: Chroma 连接失败: %s", str(e).split("\n")[0][:150])
        logger.warning(
            "[CHROMA HEALTH] connected=False error=%s",
            str(e).split("\n")[0][:150],
        )
        return False


def _check_rag() -> bool:
    """检测 Chroma 向量库连接是否正常。

    如果 collection 不存在则自动创建，创建失败才返回 unhealthy。
    向量库为空（无向量数据）视为 healthy，因为系统可以正常运行。
    """
    return _ensure_chroma_collection()


@router.get("/health")
async def health_check(request: Request):
    """生产级健康检查 — 多维度检测服务状态。

    返回值:
    - status: "healthy" | "unhealthy"
    - backend: bool  — 始终为 True（请求已到达此端点）
    - database: bool — SQLite 连接状态
    - rag: bool       — Chroma 向量库连接状态
    - timestamp: str  — ISO 8601 检查时间

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
    rag_ok = _check_rag()

    all_healthy = database_ok and rag_ok

    response_data = HealthResponse(
        status="healthy" if all_healthy else "unhealthy",
        backend=True,
        database=database_ok,
        rag=rag_ok,
        timestamp=datetime.now(timezone.utc).isoformat(),
    )

    status_code = 200 if all_healthy else 503
    return JSONResponse(content=response_data.model_dump(), status_code=status_code)
