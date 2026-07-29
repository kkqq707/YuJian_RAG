"""FastAPI 主入口 — 企业智库 AI API

- 不在此处调用 DeepSeek
- 不在此处重建向量库
- 不在此处下载 Embedding
- 不在此处读取全部知识库
- 推理资源通过 InferenceRuntime 统一管理 (Phase 6)
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import datetime, timezone as _timezone

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.app.api.router import api_router
from backend.app.config import get_settings
from backend.app.middleware import (
    AccessLogMiddleware,
    RequestIDMiddleware,
    RequestTimingMiddleware,
    SecurityHeadersMiddleware,
)
from backend.app.exceptions import register_exception_handlers
from backend.app.logging_config import setup_logging


# ---------------------------------------------------------------------------
# 修复 SQLite naive datetime 序列化问题
# SQLite 不存储时区信息，即使 SQLAlchemy 使用 DateTime(timezone=True)，
# 读取回来的 datetime 也是 naive 的。FastAPI jsonable_encoder 序列化
# naive datetime 时不会添加时区指示符，导致前端 JavaScript 将其误解析为本地时间。
# 此处 monkey-patch jsonable_encoder，确保所有 naive datetime 被当作 UTC 处理。
# ---------------------------------------------------------------------------
import fastapi.encoders as _encoders

_original_jsonable = _encoders.jsonable_encoder

def _tz_aware_jsonable(obj, *args, **kwargs):
    """确保 naive datetime 被标记为 UTC 后再序列化。"""
    if isinstance(obj, datetime) and obj.tzinfo is None:
        obj = obj.replace(tzinfo=_timezone.utc)
    return _original_jsonable(obj, *args, **kwargs)

_encoders.jsonable_encoder = _tz_aware_jsonable


# ---------------------------------------------------------------------------
# 日志初始化（最先执行）
# ---------------------------------------------------------------------------
setup_logging()


# ---------------------------------------------------------------------------
# 应用生命周期
# ---------------------------------------------------------------------------


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理。

    启动时加载推理运行时（Embedding、Reranker、Semaphore、Executor、HTTP Client），
    避免首次用户请求时等待。

    启动流程:
    1. 创建 InferenceRuntime → 加载模型 + 并发控制
    2. 连接 Chroma → 恢复 collection → 加载已有索引
    3. 读取数据库 → 检查知识库状态
    4. 验证 LLM 配置
    5. 数据库-Chroma 一致性检查

    禁止启动时重新生成 embedding 或重建索引。
    索引重建仅通过管理后台手动触发。
    """
    import logging
    import time
    logger = logging.getLogger(__name__)

    # ---- 启动预加载 ----
    t0 = time.perf_counter()

    # 打印启动横幅
    logger.info("=" * 60)
    logger.info("  RAG 初始化开始")
    logger.info("=" * 60)

    # ---- 1. 推理运行时（Embedding + Reranker + 并发控制） ----
    from backend.app.services.inference_runtime import (
        InferenceRuntime,
        create_inference_runtime,
    )
    runtime = create_inference_runtime()
    app.state.inference_runtime = runtime

    emb_ok = runtime.embedding_available
    emb_name = ""
    emb_path = ""
    try:
        import sys
        settings = get_settings()
        project_root = settings.PROJECT_ROOT
        if str(project_root) not in sys.path:
            sys.path.insert(0, str(project_root))
        from src.embedding_model import get_load_strategy_info
        strategy_info = get_load_strategy_info()
        emb_name = strategy_info.get("model_name", "")
        emb_path_display = strategy_info.get("model_path", "")
        if emb_path_display and emb_path_display != "<未配置>":
            emb_path = emb_path_display
    except Exception:
        pass

    # 启动日志：Embedding 摘要
    print(f"Embedding:")
    print(f"  name: {emb_name}")
    print(f"  path: {emb_path or '<未配置>'}")
    print(f"  status: {'OK' if emb_ok else 'FAILED'}")

    # ---- 数据库信息 (Phase 7) ----
    logger.info("Database:")
    from backend.app.database import get_db_type, _is_sqlite
    db_type = get_db_type()
    logger.info("  type: %s", db_type)
    if _is_sqlite():
        from sqlalchemy import text
        from backend.app.database import engine as db_engine
        try:
            with db_engine.connect() as conn:
                jm = conn.execute(text("PRAGMA journal_mode")).scalar()
                bt = settings.SQLITE_BUSY_TIMEOUT_MS
                logger.info("  journal_mode: %s", jm)
                logger.info("  busy_timeout: %dms", bt)
                logger.info("  status: [OK]")
                print(f"Database:")
                print(f"  type: SQLite")
                print(f"  journal_mode: {jm}")
                print(f"  busy_timeout: {bt}ms")
        except Exception as e:
            logger.warning("  status: [WARN] %s", str(e)[:100])

    # ---- 2. Chroma 向量库 (Phase 7: 使用统一运行时) ----
    logger.info("Chroma:")
    chroma_collection = ""
    chroma_vectors = 0
    vs_runtime = None  # 在 try 外预声明，避免后续引用导致 NameError
    try:
        from backend.app.vector_store_runtime import init_chroma_client
        from src.config import COLLECTION_NAME

        chroma_start = time.perf_counter()
        vs_runtime = init_chroma_client()
        chroma_elapsed = round(time.perf_counter() - chroma_start, 2)

        chroma_collection = vs_runtime.collection_name
        if vs_runtime.collection:
            chroma_vectors = vs_runtime.collection.count()

        logger.info("  collection: %s", chroma_collection)
        logger.info("  vectors:    %d", chroma_vectors)
        logger.info("  状态:       [OK] 已连接 (%.2fs)", chroma_elapsed)

        # 将运行时存入 app.state
        app.state.vector_store_runtime = vs_runtime
    except Exception as e:
        logger.warning("  状态:       [WARN] 连接失败: %s", str(e).split(chr(10))[0][:150])

    print(f"Chroma:")
    print(f"  collection: {chroma_collection or '(未创建)'}")
    print(f"  vectors:    {chroma_vectors}")

    # ---- 3. 文档状态 ----
    logger.info("Documents:")
    try:
        from src.knowledge_manager import init_database, get_statistics

        init_database()
        kb_stats = get_statistics()
        total = kb_stats.get("total_uploaded_files", 0)
        indexed = kb_stats.get("indexed_files", 0)
        total_chunks = kb_stats.get("total_chunks", 0)

        logger.info("  %d 个文件, %d indexed, %d chunks", total, indexed, total_chunks)
    except Exception as e:
        logger.warning("  [WARN] 读取文档状态失败: %s", str(e).split(chr(10))[0][:150])

    # ---- 4. LLM 配置 ----
    logger.info("LLM:")
    try:
        from src.config import validate_llm_config
        llm_config = validate_llm_config()
        if llm_config["valid"]:
            logger.info("  provider: %s", llm_config["detail"]["provider"])
            logger.info("  model:    %s", llm_config["detail"]["model"])
            logger.info("  状态:     [OK] 配置有效")
        else:
            logger.warning("  [WARN] 配置存在问题: %s", llm_config["issues"])
    except Exception as e:
        logger.warning("  [WARN] 配置验证失败: %s", str(e).split(chr(10))[0][:150])

    # ---- 5. JWT Secret ----
    try:
        from backend.app.services.llm_config_service import get_jwt_secret_sync
        jwt_secret = get_jwt_secret_sync()
        if jwt_secret:
            logger.info("JWT:      [OK] Secret 已就绪")
        else:
            logger.warning("JWT:      [WARN] Secret 未配置，认证功能可能不可用")
    except Exception:
        pass

    # ---- 6. 数据库-Chroma 一致性检查 (Phase 7: 使用缓存运行时) ----
    try:
        from src.knowledge_manager import get_statistics as _gs
        kb_stats = _gs()
        db_chunks = kb_stats.get("total_chunks", 0)

        # 使用缓存的 collection
        chroma_count = 0
        try:
            if vs_runtime and vs_runtime.collection:
                chroma_count = vs_runtime.collection.count()
            else:
                from src.vector_store import get_chroma_client
                from src.config import COLLECTION_NAME
                client = get_chroma_client()
                try:
                    coll = client.get_collection(COLLECTION_NAME)
                    chroma_count = coll.count()
                except Exception:
                    chroma_count = 0
        except Exception:
            chroma_count = 0

        if db_chunks > 0 and chroma_count == 0:
            logger.warning(
                "[WARN] 一致性: DB 中 %d chunks 但 Chroma 为空。"
                "建议管理员通过后台执行索引重建。",
                db_chunks,
            )
        elif chroma_count > 0 and db_chunks == 0:
            logger.warning(
                "[WARN] 一致性: Chroma 有 %d vectors 但 DB 无已索引记录。"
                "建议管理员检查索引状态。",
                chroma_count,
            )
        else:
            logger.info("一致性:  [OK] DB(%d chunks) <-> Chroma(%d vectors)",
                       db_chunks, chroma_count)
    except Exception as e:
        logger.warning("一致性:  [WARN] 检查失败（不影响启动）: %s",
                      str(e).split(chr(10))[0][:150])

    # ---- 7. 自动备份服务 ----
    logger.info("Backup:")
    try:
        from backend.app.services.backup_service import start_auto_backup, BackupService
        start_auto_backup()
        backup_service = BackupService()
        backup_status = backup_service.get_backup_status()
        logger.info("  状态:     [OK] 已启动 (间隔 24h)")
        if backup_status["last_backup_time"]:
            logger.info("  最后备份: %s", backup_status["last_backup_time"])
            logger.info("  备份大小: %.2f MB", backup_status["last_backup_size_bytes"] / (1024 * 1024))
        else:
            logger.info("  最后备份: 无")
        logger.info("  备份数量: %d", backup_status["total_backups"])
    except Exception as e:
        logger.warning("  [WARN] 自动备份启动失败: %s", str(e).split(chr(10))[0][:150])

    # ---- 8. 文档后台任务运行时 (Phase 8) ----
    logger.info("Document Tasks:")
    try:
        from backend.app.services.document_task_runtime import get_document_task_runtime
        from backend.app.services.document_task_service import DocumentTaskService

        task_runtime = get_document_task_runtime()
        task_service = DocumentTaskService()

        # 启动恢复
        recovery_result = task_service.recover_on_startup()

        await task_runtime.start(
            task_processor=task_service.process_task,
            num_workers=settings.DOCUMENT_TASK_WORKERS,
            queue_size=settings.DOCUMENT_TASK_QUEUE_SIZE,
            max_concurrent_uploads=settings.MAX_CONCURRENT_UPLOADS,
        )
        app.state.document_task_runtime = task_runtime

        logger.info("  workers:     %d", settings.DOCUMENT_TASK_WORKERS)
        logger.info("  queue_size:  %d", settings.DOCUMENT_TASK_QUEUE_SIZE)
        logger.info("  status:      [OK]")
        if recovery_result["interrupted_tasks"] > 0:
            logger.info("  恢复:        interrupted=%d, re_enqueued=%d",
                       recovery_result["interrupted_tasks"],
                       recovery_result["re_enqueued_pending"])
    except Exception as e:
        logger.warning("  [WARN] 文档任务运行时启动失败: %s",
                      str(e).split(chr(10))[0][:150])

    total_elapsed = round(time.perf_counter() - t0, 2)
    logger.info("=" * 60)
    logger.info("  RAG ready. 总耗时 %.2fs", total_elapsed)
    logger.info("=" * 60)

    print("")
    print("RAG: READY")

    yield
    # 关闭时
    from backend.app.services.backup_service import stop_auto_backup
    stop_auto_backup()

    # Phase 8: 关闭文档任务运行时
    try:
        _task_runtime = getattr(app.state, "document_task_runtime", None)
        if _task_runtime:
            await _task_runtime.stop(graceful=True, timeout=30.0)
    except Exception as e:
        logger.warning("关闭文档任务运行时失败: %s", str(e)[:200])

    # 关闭推理运行时
    await runtime.close()
    logger.info("FastAPI 应用关闭")


# ---------------------------------------------------------------------------
# 创建应用
# ---------------------------------------------------------------------------


def create_app() -> FastAPI:
    """创建并配置 FastAPI 应用。"""
    settings = get_settings()

    app = FastAPI(
        title=settings.APP_NAME,
        version=settings.APP_VERSION,
        description="企业知识库 RAG 问答系统 — REST API",
        docs_url="/docs",
        redoc_url="/redoc",
        lifespan=lifespan,
    )

    # ---- CORS ----
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # ---- 安全响应头 ----
    app.add_middleware(SecurityHeadersMiddleware)

    # ---- 自定义中间件 ----
    app.add_middleware(RequestIDMiddleware)
    app.add_middleware(AccessLogMiddleware)
    app.add_middleware(RequestTimingMiddleware)

    # ---- 路由 ----
    app.include_router(api_router)

    # ---- 模型健康检查（独立路由，无 /v1 前缀） ----
    from backend.app.api.routes import model_health
    app.include_router(model_health.router)

    # ---- 根路径 ----
    @app.get("/")
    async def root():
        return {
            "name": settings.APP_NAME,
            "docs": "/docs",
        }

    # ---- 异常处理 ----
    register_exception_handlers(app)

    return app


# ---------------------------------------------------------------------------
# 应用实例
# ---------------------------------------------------------------------------

app = create_app()
