"""系统状态服务 — 提供安全的系统诊断信息

- 不返回 API Key
- 不返回完整 Base URL
- 不返回绝对路径
- 不返回环境变量内容
"""

from __future__ import annotations

import logging
import sys
from typing import Optional

from backend.app.config import get_settings
from backend.app.services.rag_adapter import get_rag_adapter

logger = logging.getLogger(__name__)


class SystemService:
    """系统状态查询服务。"""

    def get_status(self) -> dict:
        """获取安全的系统状态信息。

        Returns
        -------
        dict
        """
        settings = get_settings()
        project_root = settings.PROJECT_ROOT

        # 确保项目根在 sys.path 中
        if str(project_root) not in sys.path:
            sys.path.insert(0, str(project_root))

        # 向量库状态（通过 RAGAdapter.health_check，不加载重模型）
        adapter = get_rag_adapter()
        rag_health = adapter.health_check()

        # LLM 配置状态（安全地获取）
        llm_info = self._get_llm_info()

        # 整体状态判定
        overall = "ok"
        if rag_health["vector_store"] == "not_found":
            overall = "degraded"

        return {
            "status": overall,
            "vector_store": rag_health["vector_store"],
            "knowledge_chunks": rag_health["knowledge_chunks"],
            "knowledge_files": self._get_file_count(),
            "enterprise_name": getattr(settings, "ENTERPRISE_NAME", "企业智库 AI"),
            "llm_configured": llm_info["configured"],
            "llm_provider": llm_info["provider"],
            "model_name": llm_info["model"],
        }

    def get_rag_health(self) -> dict:
        """获取 RAG 完整健康检查信息。

        包含 Chroma 状态、文档状态、Embedding 模型状态、
        最近索引任务状态、备份状态等详细信息。

        供管理员首页系统健康面板使用。

        Returns
        -------
        dict
            {
                "status": "healthy" | "degraded" | "unhealthy",
                "chroma": {...},
                "documents": {...},
                "embedding": {...},
                "last_index_task": {...},
                "last_index_time": str,
                "backup": {...},
            }
        """
        settings = get_settings()
        project_root = settings.PROJECT_ROOT

        if str(project_root) not in sys.path:
            sys.path.insert(0, str(project_root))

        result = {
            "status": "healthy",
            "chroma": {
                "collections": 0,
                "vectors": 0,
                "status": "not_found",
            },
            "documents": {
                "total": 0,
                "indexed": 0,
                "failed": 0,
                "pending": 0,
            },
            "embedding": {
                "model": "",
                "loaded": False,
                "model_path": "",
                "load_method": "",
            },
            "last_index_task": None,
            "last_index_time": None,
            "backup": {
                "last_backup_time": None,
                "last_backup_size_bytes": 0,
                "last_backup_file": None,
                "total_backups": 0,
                "total_backups_size_bytes": 0,
                "status": "no_backup",
            },
        }

        try:
            # ---- Chroma 状态 ----
            # Chroma v0.6.x 兼容: 使用 get_or_create_collection 确保 collection 可访问，
            # 不依赖 list_collections() 的字符串匹配
            try:
                from src.vector_store import get_chroma_client, get_or_create_collection
                from src.config import COLLECTION_NAME

                client = get_chroma_client()
                try:
                    collection = get_or_create_collection()
                    chroma_count = collection.count()
                    result["chroma"] = {
                        "collections": 1,
                        "vectors": chroma_count,
                        "status": "ok",
                    }
                    logger.info(
                        "[CHROMA HEALTH] connected=True collection=%s count=%s",
                        COLLECTION_NAME, chroma_count,
                    )
                except Exception:
                    result["chroma"] = {
                        "collections": 0,
                        "vectors": 0,
                        "status": "collection_not_found",
                    }
                    logger.warning(
                        "[CHROMA HEALTH] connected=False collection_not_found=%s",
                        COLLECTION_NAME,
                    )
            except Exception as e:
                result["chroma"] = {
                    "collections": 0,
                    "vectors": 0,
                    "status": "error",
                    "error": str(e).split("\n")[0][:200],
                }
                logger.warning(
                    "[CHROMA HEALTH] connected=False error=%s",
                    str(e).split("\n")[0][:150],
                )

            # ---- 文档状态 ----
            try:
                from src.knowledge_manager import get_statistics as get_kb_stats
                kb_stats = get_kb_stats()
                total = kb_stats.get("total_uploaded_files", 0)
                indexed = kb_stats.get("indexed_files", 0)
                result["documents"]["total"] = total
                result["documents"]["indexed"] = indexed
                result["documents"]["last_update_time"] = kb_stats.get("last_update_time")

                # 获取失败和待处理的文件数
                try:
                    from src.knowledge_manager import get_all_active_files
                    all_files = get_all_active_files(source_type="upload")
                    failed_count = sum(1 for f in all_files if f.get("index_status") == "failed")
                    pending_count = sum(1 for f in all_files if f.get("index_status") == "pending")
                    result["documents"]["failed"] = failed_count
                    result["documents"]["pending"] = pending_count
                except Exception:
                    pass
            except Exception:
                pass

            # ---- Embedding 状态 ----
            try:
                from src.embedding_model import (
                    get_load_strategy_info,
                    is_model_available_locally,
                    EMBEDDING_MODEL_NAME,
                )
                strategy_info = get_load_strategy_info()
                result["embedding"] = {
                    "model": EMBEDDING_MODEL_NAME or strategy_info.get("model_name", ""),
                    "loaded": is_model_available_locally(),
                    "model_path": strategy_info.get("model_path", ""),
                    "load_method": strategy_info.get("load_method", ""),
                }
            except Exception:
                result["embedding"] = {
                    "model": "",
                    "loaded": False,
                    "model_path": "",
                    "load_method": "error",
                }

            # ---- 最近索引任务 ----
            try:
                from src.knowledge_manager import get_latest_index_task
                latest_task = get_latest_index_task()
                if latest_task:
                    result["last_index_task"] = {
                        "id": latest_task.get("id"),
                        "status": latest_task.get("status"),
                        "progress": latest_task.get("progress", 0),
                        "total_files": latest_task.get("total_files", 0),
                        "success_count": latest_task.get("success_count", 0),
                        "failed_count": latest_task.get("failed_count", 0),
                        "total_chunks": latest_task.get("total_chunks", 0),
                        "start_time": latest_task.get("start_time"),
                        "end_time": latest_task.get("end_time"),
                    }
                    result["last_index_time"] = latest_task.get("end_time") or latest_task.get("start_time")
                else:
                    result["last_index_time"] = kb_stats.get("last_update_time") if 'kb_stats' in dir() else None
            except Exception:
                pass

            # ---- 备份状态 ----
            try:
                from backend.app.services.backup_service import BackupService
                backup_service = BackupService()
                backup_status = backup_service.get_backup_status()
                result["backup"] = backup_status
            except Exception:
                pass

            # ---- 整体状态判定 ----
            chroma_ok = result["chroma"]["status"] == "ok"
            has_vectors = result["chroma"]["vectors"] > 0
            has_documents = result["documents"]["total"] > 0
            all_indexed = (
                result["documents"]["total"] > 0
                and result["documents"]["indexed"] >= result["documents"]["total"]
            )
            has_failures = result["documents"]["failed"] > 0

            if not chroma_ok and has_documents:
                # Chroma 向量库不可用但有文档 → 严重问题，需要检查 Chroma 服务
                result["status"] = "unhealthy"
            elif has_documents and all_indexed and has_vectors:
                # 所有文档已成功索引，向量库正常 → 健康
                result["status"] = "healthy"
            elif has_documents and not has_vectors:
                # 有文档但向量库为空 → 需要重建索引
                result["status"] = "degraded"
            elif has_failures and has_vectors:
                # 部分文档索引失败但已有向量数据 → 部分降级
                result["status"] = "degraded"
            else:
                result["status"] = "healthy"

        except Exception as e:
            logger.warning("RAG 健康检查部分失败: %s", e)

        return result

    def get_model_health(self) -> dict:
        """获取 Embedding 和 Reranker 模型健康状态。

        供企业离线部署诊断使用。Phase 6: 优先使用 InferenceRuntime。

        Returns
        -------
        dict
            {
                "embedding": {"name": str, "loaded": bool, "path": str, "load_mode": str},
                "reranker": {"name": str, "loaded": bool, "path": str, "load_mode": str},
            }
        """
        settings = get_settings()
        project_root = settings.PROJECT_ROOT

        if str(project_root) not in sys.path:
            sys.path.insert(0, str(project_root))

        result = {
            "embedding": {
                "name": "",
                "loaded": False,
                "path": "",
                "load_mode": "unknown",
            },
            "reranker": {
                "name": "",
                "loaded": False,
                "path": "",
                "load_mode": "unknown",
            },
        }

        # ---- Embedding (优先从 InferenceRuntime) ----
        try:
            from src.embedding_model import (
                get_load_strategy_info,
                is_model_available_locally,
                EMBEDDING_MODEL_NAME,
            )
            strategy_info = get_load_strategy_info()
            result["embedding"] = {
                "name": EMBEDDING_MODEL_NAME,
                "loaded": is_model_available_locally(),
                "path": strategy_info.get("model_path", ""),
                "load_mode": strategy_info.get("load_method", ""),
            }
        except Exception as e:
            result["embedding"]["load_mode"] = f"error: {str(e)[:100]}"

        # ---- Reranker (优先从 InferenceRuntime) ----
        try:
            from backend.app.services.inference_runtime import InferenceRuntime
            # 尝试从 FastAPI app state 获取 runtime
            # 如果不可用，回退到直接加载
            from src.reranker import get_reranker
            reranker = get_reranker()
            reranker.ensure_initialized()
            result["reranker"] = {
                "name": reranker.model_name,
                "loaded": reranker.is_available(),
                "path": reranker.model_path or "",
                "load_mode": "local" if reranker.is_available() else "not_found",
            }
        except Exception as e:
            result["reranker"]["load_mode"] = f"error: {str(e)[:100]}"

        return result

    def get_inference_metrics(self) -> dict:
        """获取推理运行时指标（仅管理员可访问）。

        Phase 6: 进程内推理指标快照。
        """
        try:
            from backend.app.services.inference_runtime import InferenceRuntime
            # 尝试获取运行时（从全局引用）
            import asyncio
            # 这里无法直接访问 app.state，返回空指标
            return {
                "available": False,
                "message": "推理运行时指标不可用（需通过依赖注入访问）",
            }
        except ImportError:
            return {"available": False, "message": "推理运行时未加载"}

    def _get_file_count(self) -> int:
        """安全获取知识库文件数量（不上传时读取，不返回路径）。"""
        try:
            from src.knowledge_manager import get_statistics
            stats = get_statistics()
            return stats.get("total_uploaded_files", 0)
        except Exception:
            return 0

    def _get_llm_info(self) -> dict:
        """安全获取 LLM 配置信息 — 仅从数据库读取，不泄露 API Key。"""
        try:
            from backend.app.services.llm_config_service import get_current_llm_config
            llm = get_current_llm_config()
            return {
                "configured": llm["configured"],
                "provider": llm["provider"],
                "model": llm["model"],
                "source": llm["source"],
            }
        except Exception:
            return {
                "configured": False,
                "provider": None,
                "model": None,
                "source": None,
            }


# ---------------------------------------------------------------------------
# 单例
# ---------------------------------------------------------------------------


_system_service: Optional[SystemService] = None


def get_system_service() -> SystemService:
    """获取缓存的 SystemService 单例。"""
    global _system_service
    if _system_service is None:
        _system_service = SystemService()
    return _system_service
