"""管理员系统管理服务

提供:
- 完整系统状态诊断
- Embedding / DeepSeek / Chroma / SQLite 状态
- 统计信息（文件、用户、Chunk 等）
- 审计日志查询（增强过滤）
- 系统健康检查
- 系统信息

安全:
- 不返回 API Key
- 不返回绝对路径
- 不返回环境变量
"""

from __future__ import annotations

import logging
import sys
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from backend.app.config import get_settings
from backend.app.models.user import User
from backend.app.models.admin_audit_log import ACTION_MODULE_MAP, AUDIT_MODULES

logger = logging.getLogger(__name__)


class AdminSystemService:
    """管理员系统管理服务。"""

    def __init__(self, db: Session):
        self.db = db
        self.settings = get_settings()

    # ------------------------------------------------------------------
    # 完整系统状态
    # ------------------------------------------------------------------

    def get_full_status(self) -> dict:
        """获取完整系统诊断信息。

        Returns
        -------
        dict
        """
        # 收集各组件状态
        embedding_status = self._check_embedding()
        deepseek_status = self._check_deepseek()
        chroma_status = self._check_chroma()
        sqlite_status = self._check_sqlite()

        # 统计
        stats = self._get_stats()

        # 整体状态
        components = [embedding_status, deepseek_status, chroma_status, sqlite_status]
        if any(c["status"] == "error" for c in components):
            overall = "error"
        elif any(c["status"] in ("not_found", "not_configured") for c in components):
            overall = "degraded"
        else:
            overall = "ok"

        return {
            "success": True,
            "version": self.settings.APP_VERSION,
            "overall_status": overall,
            "embedding": embedding_status,
            "deepseek": deepseek_status,
            "chroma": chroma_status,
            "sqlite": sqlite_status,
            "stats": stats,
        }

    def _check_embedding(self) -> dict:
        """检查 Embedding 模型状态（增强版 — 含模型名称、路径、加载方式）。"""
        self._ensure_src_path()
        try:
            from src.embedding_model import (
                get_embedding_device,
                get_load_strategy_info,
            )
            from src.config import EMBEDDING_MODEL_NAME

            device = get_embedding_device()
            strategy_info = get_load_strategy_info()

            return {
                "status": "ok",
                "detail": f"{EMBEDDING_MODEL_NAME} (device={device})",
                "model_name": EMBEDDING_MODEL_NAME,
                "model_path": strategy_info.get("model_path", ""),
                "load_method": strategy_info.get("load_method", ""),
                "strategy": strategy_info.get("strategy", ""),
            }
        except Exception as e:
            return {
                "status": "error",
                "detail": str(e).split("\n")[0][:100],
                "model_name": "",
                "model_path": "",
                "load_method": "",
                "strategy": "",
            }

    def _check_deepseek(self) -> dict:
        """检查 DeepSeek / LLM 状态（仅从数据库读取配置）。"""
        try:
            from backend.app.services.llm_config_service import get_current_llm_config

            llm = get_current_llm_config()

            if not llm["configured"]:
                provider_text = f" ({llm['provider']})" if llm["provider"] else ""
                return {
                    "status": "not_configured",
                    "detail": f"LLM{provider_text} 未配置",
                }

            return {
                "status": "ok",
                "detail": f"provider={llm['provider']}, model={llm['model']}",
            }
        except Exception as e:
            return {"status": "error", "detail": str(e).split("\n")[0][:100]}

    def _check_chroma(self) -> dict:
        """检查 Chroma 向量库状态（Phase 7: 使用缓存运行时）。

        优先使用 VectorStoreRuntime 中的缓存 client/collection，
        避免重复创建 PersistentClient 导致 SQLite 文件锁冲突。
        """
        self._ensure_src_path()
        try:
            from backend.app.vector_store_runtime import get_vector_store_runtime
            from src.config import COLLECTION_NAME

            runtime = get_vector_store_runtime()
            if runtime.is_initialized() and runtime.collection is not None:
                count = runtime.collection.count()
                logger.info(
                    "[CHROMA HEALTH] connected=True collection=%s count=%s (cached)",
                    COLLECTION_NAME, count,
                )
                return {
                    "status": "ok",
                    "detail": f"已就绪，{count} 个向量",
                }

            # 回退到直接访问
            from src.vector_store import get_chroma_client, get_or_create_collection
            client = get_chroma_client()
            collection = get_or_create_collection()
            count = collection.count()

            logger.info(
                "[CHROMA HEALTH] connected=True collection=%s count=%s (fallback)",
                COLLECTION_NAME, count,
            )
            return {
                "status": "ok",
                "detail": f"已就绪，{count} 个向量",
            }
        except Exception as e:
            logger.warning(
                "[CHROMA HEALTH] connected=False error=%s",
                str(e).split("\n")[0][:150],
            )
            return {"status": "error", "detail": str(e).split("\n")[0][:100]}

    def _check_sqlite(self) -> dict:
        """检查 SQLite 数据库状态（Phase 7: 增强版）。"""
        try:
            from backend.app.database import engine, get_db_type, _is_sqlite
            from sqlalchemy import text

            db_type = get_db_type()
            result = {
                "status": "ok",
                "detail": "数据库连接正常",
                "type": db_type,
            }

            if _is_sqlite():
                with engine.connect() as conn:
                    jm = conn.execute(text("PRAGMA journal_mode")).scalar()
                    result["journal_mode"] = jm
                    result["busy_timeout_ms"] = self.settings.SQLITE_BUSY_TIMEOUT_MS

            # 执行简单查询验证
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))

            return result
        except Exception as e:
            return {
                "status": "error",
                "detail": str(e).split("\n")[0][:100],
                "type": "unknown",
            }

    def _get_stats(self) -> dict:
        """收集系统统计信息。"""
        self._ensure_src_path()

        # 用户统计
        total_users = self.db.execute(
            select(func.count()).select_from(User)
        ).scalar_one()

        active_users = self.db.execute(
            select(func.count()).select_from(User).where(User.is_active == True)
        ).scalar_one()

        admin_users = self.db.execute(
            select(func.count()).select_from(User).where(
                User.is_active == True, User.role == "admin"
            )
        ).scalar_one()

        # 今日问答数（从 chat_messages 表统计今日用户问题，排除测试数据）
        today_questions = 0
        try:
            from backend.app.models.chat import ChatMessage
            today_start = datetime.now(timezone.utc).replace(
                hour=0, minute=0, second=0, microsecond=0
            )
            today_questions = self.db.execute(
                select(func.count()).select_from(ChatMessage).where(
                    ChatMessage.role == "user",
                    ChatMessage.is_test == False,
                    ChatMessage.created_at >= today_start,
                )
            ).scalar_one()
        except Exception:
            pass

        # 知识库统计
        total_files = 0
        indexed_files = 0
        total_chunks = 0
        chroma_vectors = 0
        last_index_update = None
        recent_uploads = []

        try:
            from src.knowledge_manager import init_database, get_statistics, get_all_active_files
            init_database()
            kb_stats = get_statistics()
            total_files = kb_stats.get("total_uploaded_files", 0)
            indexed_files = kb_stats.get("indexed_files", 0)
            total_chunks = kb_stats.get("total_chunks", 0)
            last_index_update = kb_stats.get("last_update_time")

            # 最近 5 个上传文件
            try:
                all_files = get_all_active_files(source_type="upload")
                recent_uploads = [
                    {
                        "id": f.get("id"),
                        "original_name": f.get("original_name"),
                        "file_type": f.get("file_type"),
                        "index_status": f.get("index_status"),
                        "upload_time": f.get("upload_time"),
                        "chunk_count": f.get("chunk_count", 0),
                    }
                    for f in all_files[:5]
                ]
            except Exception:
                pass
        except Exception:
            pass

        try:
            from src.vector_store import get_or_create_collection
            collection = get_or_create_collection()
            chroma_vectors = collection.count()
        except Exception:
            pass

        # RAG 配置
        embedding_model = ""
        embedding_model_path = ""
        embedding_load_method = ""
        chroma_collection = ""
        llm_provider = None
        model_name = None

        try:
            from src.config import (
                EMBEDDING_MODEL_NAME,
                EMBEDDING_MODEL_PATH,
                COLLECTION_NAME,
            )
            embedding_model = EMBEDDING_MODEL_NAME
            embedding_model_path = EMBEDDING_MODEL_PATH or ""
            chroma_collection = COLLECTION_NAME
        except Exception:
            pass

        # 获取实际加载策略信息
        try:
            from src.embedding_model import get_load_strategy_info
            strategy_info = get_load_strategy_info()
            embedding_load_method = strategy_info.get("load_method", "")
            if not embedding_model_path:
                embedding_model_path = strategy_info.get("model_path", "")
        except Exception:
            pass

        # 从 AI 服务配置中心获取实际生效的 LLM 配置
        try:
            from backend.app.services.llm_config_service import get_current_llm_config
            llm_config = get_current_llm_config()
            if llm_config["configured"]:
                llm_provider = llm_config["provider"]
                model_name = llm_config["model"]
        except Exception:
            pass

        return {
            "total_files": total_files,
            "indexed_files": indexed_files,
            "total_chunks": total_chunks,
            "chroma_vectors": chroma_vectors,
            "total_users": total_users,
            "active_users": active_users,
            "admin_users": admin_users,
            "today_questions": today_questions,
            "recent_uploads": recent_uploads,
            "embedding_model": embedding_model,
            "embedding_model_path": embedding_model_path,
            "embedding_load_method": embedding_load_method,
            "chroma_collection": chroma_collection,
            "llm_provider": llm_provider,
            "model_name": model_name,
            "last_index_update": last_index_update,
        }

    # ------------------------------------------------------------------
    # 审计日志
    # ------------------------------------------------------------------

    def get_audit_logs(
        self,
        skip: int = 0,
        limit: int = 100,
        action: Optional[str] = None,
        admin_id: Optional[int] = None,
    ) -> dict:
        """获取审计日志列表。"""
        from backend.app.repositories.audit_log_repository import AuditLogRepository

        repo = AuditLogRepository(self.db)
        logs = repo.list_logs(skip=skip, limit=limit, action=action, admin_id=admin_id)
        total = repo.count_logs(action=action, admin_id=admin_id)

        return {
            "success": True,
            "total": total,
            "logs": [
                {
                    "id": log.id,
                    "admin_id": log.admin_id,
                    "admin_username": log.admin_username,
                    "action": log.action,
                    "target_type": log.target_type,
                    "target_id": log.target_id,
                    "detail": log.detail,
                    "ip_address": log.ip_address,
                    "created_at": log.created_at.isoformat() if log.created_at else None,
                }
                for log in logs
            ],
        }

    # ------------------------------------------------------------------
    # 系统日志（增强版）
    # ------------------------------------------------------------------

    def get_system_logs(
        self,
        page: int = 1,
        page_size: int = 50,
        module: Optional[str] = None,
        status: Optional[str] = None,
        username: Optional[str] = None,
        start_time: Optional[str] = None,
        end_time: Optional[str] = None,
    ) -> dict:
        """获取系统日志列表（增强过滤）。

        Parameters
        ----------
        page : int
        page_size : int
        module : str, optional
            模块过滤
        status : str, optional
            状态过滤: success | failed | warning
        username : str, optional
            用户名模糊搜索
        start_time : str, optional
            开始时间 ISO 格式
        end_time : str, optional
            结束时间 ISO 格式

        Returns
        -------
        dict
        """
        from backend.app.repositories.audit_log_repository import AuditLogRepository

        skip = (page - 1) * page_size

        # 解析时间
        start_dt = None
        end_dt = None
        if start_time:
            try:
                start_dt = datetime.fromisoformat(start_time)
            except ValueError:
                pass
        if end_time:
            try:
                end_dt = datetime.fromisoformat(end_time)
            except ValueError:
                pass

        repo = AuditLogRepository(self.db)
        logs = repo.list_logs(
            skip=skip,
            limit=page_size,
            module=module,
            status=status,
            username=username,
            start_time=start_dt,
            end_time=end_dt,
        )
        total = repo.count_logs(
            module=module,
            status=status,
            username=username,
            start_time=start_dt,
            end_time=end_dt,
        )

        return {
            "success": True,
            "total": total,
            "items": [
                {
                    "id": log.id,
                    "user_id": log.admin_id,
                    "username": log.admin_username,
                    "module": log.module,
                    "action": log.action,
                    "status": log.status or "success",
                    "target_type": log.target_type,
                    "target_id": log.target_id,
                    "detail": log.detail,
                    "ip_address": log.ip_address,
                    "created_at": log.created_at.isoformat() if log.created_at else None,
                }
                for log in logs
            ],
        }

    def get_system_log_detail(self, log_id: int) -> Optional[dict]:
        """获取单条日志详情。"""
        from backend.app.models.admin_audit_log import AdminAuditLog

        stmt = select(AdminAuditLog).where(AdminAuditLog.id == log_id)
        log = self.db.execute(stmt).scalar_one_or_none()

        if log is None:
            return None

        return {
            "id": log.id,
            "user_id": log.admin_id,
            "username": log.admin_username,
            "module": log.module,
            "action": log.action,
            "status": log.status or "success",
            "target_type": log.target_type,
            "target_id": log.target_id,
            "detail": log.detail,
            "ip_address": log.ip_address,
            "user_agent": log.user_agent,
            "created_at": log.created_at.isoformat() if log.created_at else None,
        }

    # ------------------------------------------------------------------
    # 健康检查
    # ------------------------------------------------------------------

    def get_health_check(self) -> dict:
        """系统健康检查。

        Returns
        -------
        dict
            {"backend": bool, "database": bool, "chroma": bool, "chroma_detail": str,
             "llm": bool, "embedding": bool}
        """
        result = {
            "success": True,
            "backend": True,  # 服务在运行就能响应
            "database": False,
            "chroma": False,
            "chroma_detail": "",
            "llm": False,
            "embedding": False,
        }

        # Database
        try:
            from backend.app.database import engine
            with engine.connect() as conn:
                conn.execute(select(1))
            result["database"] = True
        except Exception:
            pass

        # Chroma — 必须使用与 RAG 完全相同的 get_chroma_client() 单例
        # 禁止创建新的 PersistentClient，否则会因 SQLite 文件锁冲突导致检测失败
        #
        # 健康检查逻辑（Chromav0.6.x 兼容）:
        #   1. Chroma client 连接成功
        #   2. target collection 存在且可访问
        #   3. collection.count() >= 0
        # 以上全部满足 → healthy。不要求向量库必须有数据。
        try:
            self._ensure_src_path()
            from src.vector_store import get_chroma_client, get_or_create_collection
            from src.config import COLLECTION_NAME

            client = get_chroma_client()

            # Chroma v0.6.x: list_collections() 仅返回 collection 名称字符串，
            # 直接使用 get_or_create_collection() 确保 collection 存在且可访问
            collection = get_or_create_collection()
            count = collection.count()

            result["chroma"] = True
            result["chroma_detail"] = f"正常，向量数: {count}"

            logger.info(
                "[CHROMA HEALTH] connected=True collection=%s count=%s",
                COLLECTION_NAME, count,
            )
        except Exception as e:
            result["chroma_detail"] = str(e).split("\n")[0][:120]
            logger.warning(
                "[CHROMA HEALTH] connected=False error=%s",
                str(e).split("\n")[0][:150],
            )

        # LLM — 仅从数据库配置检查
        try:
            from backend.app.services.llm_config_service import get_current_llm_config
            llm_config = get_current_llm_config()
            if llm_config["configured"]:
                result["llm"] = True
        except Exception:
            pass

        # Embedding
        try:
            self._ensure_src_path()
            from src.embedding_model import get_embedding_model
            get_embedding_model()
            result["embedding"] = True
        except Exception:
            pass

        return result

    # ------------------------------------------------------------------
    # 系统信息
    # ------------------------------------------------------------------

    def get_system_info(self) -> dict:
        """获取系统基本信息。"""
        self._ensure_src_path()

        settings = get_settings()

        # 检测数据库类型
        db_type = "SQLite"
        if "postgresql" in settings.DATABASE_URL.lower():
            db_type = "PostgreSQL"
        elif "mysql" in settings.DATABASE_URL.lower():
            db_type = "MySQL"

        # 获取当前 LLM 模型 — 仅从数据库配置读取
        model_name = None
        try:
            from backend.app.services.llm_config_service import get_current_llm_config
            llm_config = get_current_llm_config()
            if llm_config["configured"]:
                model_name = llm_config["model"]
        except Exception:
            pass

        return {
            "success": True,
            "app_name": settings.APP_NAME,
            "version": settings.APP_VERSION,
            "deploy_mode": "单企业版",
            "database_type": db_type,
            "vector_store": "Chroma",
            "model_name": model_name,
        }

    # ------------------------------------------------------------------
    # 模块列表
    # ------------------------------------------------------------------

    def get_module_list(self) -> list[dict]:
        """获取可用的模块列表。"""
        return [
            {"value": key, "label": label}
            for key, label in AUDIT_MODULES.items()
        ]

    # ------------------------------------------------------------------
    # 内部
    # ------------------------------------------------------------------

    @staticmethod
    def _ensure_src_path():
        """确保项目根在 sys.path 中。"""
        project_root = get_settings().PROJECT_ROOT
        if str(project_root) not in sys.path:
            sys.path.insert(0, str(project_root))
