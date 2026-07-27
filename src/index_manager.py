"""索引管理模块

提供上传文件向量化和索引管理功能:
- 增量索引上传文件
- 单文件索引/重索引
- 单文件从索引中删除
- 全量重建索引
- 索引统计

安全策略:
- 索引时不调用 DeepSeek
- 使用 upload_id 关联所有 chunk
- 删除只影响目标文件的 chunks
- 文件级锁避免并发索引同一文件
"""

from __future__ import annotations

import logging
import time
import threading
from pathlib import Path
from typing import Optional

from langchain_core.documents import Document

from src.config import (
    UPLOADS_DATA_DIR,
    COLLECTION_NAME,
    CHROMA_DIR,
)
from src.knowledge_manager import (
    get_file_by_id,
    get_pending_files,
    update_index_status,
    INDEX_STATUS_PENDING,
    INDEX_STATUS_PROCESSING,
    INDEX_STATUS_INDEXED,
    INDEX_STATUS_FAILED,
    INDEX_STATUS_DELETED,
    SOURCE_TYPE_UPLOAD,
    EMBEDDING_STATUS_PENDING,
    EMBEDDING_STATUS_EMBEDDING,
    EMBEDDING_STATUS_COMPLETED,
    EMBEDDING_STATUS_FAILED,
    INDEX_TASK_PREPARING,
    INDEX_TASK_CLEANING,
    INDEX_TASK_REPARSING,
    INDEX_TASK_EMBEDDING,
    INDEX_TASK_WRITING,
    INDEX_TASK_COMPLETED,
    INDEX_TASK_FAILED,
    create_index_task,
    update_index_task,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# 文件级锁
# ---------------------------------------------------------------------------

_index_locks: dict[str, threading.Lock] = {}
_locks_guard = threading.Lock()


def _get_file_lock(upload_id: str) -> threading.Lock:
    """获取文件级别的锁，避免同一文件并发索引。"""
    with _locks_guard:
        if upload_id not in _index_locks:
            _index_locks[upload_id] = threading.Lock()
        return _index_locks[upload_id]


# ---------------------------------------------------------------------------
# 公开函数
# ---------------------------------------------------------------------------


def index_uploaded_files(
    progress_callback: callable | None = None,
) -> dict:
    """索引所有待处理的已上传文件。

    从 knowledge_manager 获取 index_status 为 pending 或 failed 的文件，
    逐个进行向量化。

    Parameters
    ----------
    progress_callback : callable, optional
        进度回调函数，签名: callback(stage: str, detail: str, current: int, total: int)

    Returns
    -------
    dict
        {
            "success": bool,
            "total": int,
            "indexed": int,
            "failed": int,
            "total_chunks": int,
            "elapsed_seconds": float,
            "errors": list[str],
        }
    """
    t_start = time.perf_counter()

    pending_files = get_pending_files()
    result = {
        "success": True,
        "total": len(pending_files),
        "indexed": 0,
        "failed": 0,
        "total_chunks": 0,
        "elapsed_seconds": 0.0,
        "errors": [],
    }

    if not pending_files:
        result["elapsed_seconds"] = round(time.perf_counter() - t_start, 2)
        return result

    if progress_callback:
        progress_callback("准备索引", f"发现 {len(pending_files)} 个待处理文件", 0, len(pending_files))

    for i, file_record in enumerate(pending_files):
        file_id = file_record["id"]
        original_name = file_record.get("original_name", "未知")

        if progress_callback:
            progress_callback(
                "正在索引",
                f"({i + 1}/{len(pending_files)}) {original_name}",
                i + 1,
                len(pending_files),
            )

        try:
            chunk_count = index_single_file(file_id, progress_callback)
            result["indexed"] += 1
            result["total_chunks"] += chunk_count
        except Exception as e:
            result["failed"] += 1
            error_msg = _safe_str(e)
            result["errors"].append(f"{original_name}: {error_msg}")
            try:
                update_index_status(file_id, INDEX_STATUS_FAILED, error_message=error_msg)
            except Exception:
                pass

    result["success"] = result["failed"] == 0
    result["elapsed_seconds"] = round(time.perf_counter() - t_start, 2)
    return result


def index_single_file(
    upload_id: str,
    progress_callback: callable | None = None,
) -> int:
    """索引单个上传文件。

    流程:
    1. 获取文件锁
    2. 从磁盘读取文件
    3. 加载并切分文档
    4. 删除旧 chunks（如存在）
    5. 生成向量并写入 Chroma
    6. 更新元数据状态

    Parameters
    ----------
    upload_id : str
        文件记录 ID
    progress_callback : callable, optional

    Returns
    -------
    int
        生成的 chunk 数量

    Raises
    ------
    ValueError
        文件记录不存在或状态不允许
    RuntimeError
        索引过程失败
    """
    lock = _get_file_lock(upload_id)
    if not lock.acquire(blocking=False):
        raise RuntimeError(f"文件正在被另一个索引任务处理: {upload_id}")

    try:
        file_record = get_file_by_id(upload_id)
        if not file_record:
            raise ValueError(f"文件记录不存在: {upload_id}")
        if not file_record.get("is_active"):
            raise ValueError(f"文件已被删除: {upload_id}")

        original_name = file_record.get("original_name", "未知")
        stored_name = file_record.get("stored_name", "")
        file_type = file_record.get("file_type", "")

        # 更新状态为 processing + embedding_status=pending
        update_index_status(upload_id, INDEX_STATUS_PROCESSING,
                          embedding_status=EMBEDDING_STATUS_PENDING)

        # 构建文件路径
        file_path = UPLOADS_DATA_DIR / stored_name
        if not file_path.is_file():
            raise FileNotFoundError(f"文件不存在: {file_path}")

        if progress_callback:
            progress_callback("正在解析", f"读取文件: {original_name}", 0, 0)

        # 1. 加载文档
        from src.document_loader import load_single_file
        documents = load_single_file(file_path)

        # 为所有 document 添加 upload 相关 metadata
        # 获取 tenant_id
        tenant_id = file_record.get("tenant_id", "default")
        for doc in documents:
            doc.metadata["upload_id"] = upload_id
            doc.metadata["source_type"] = SOURCE_TYPE_UPLOAD
            doc.metadata["original_name"] = original_name
            doc.metadata["knowledge_source"] = SOURCE_TYPE_UPLOAD
            doc.metadata["tenant_id"] = tenant_id

        if not documents:
            raise ValueError("文档解析后为空，请检查文件内容")

        if progress_callback:
            progress_callback("正在切分", f"文本切分: {original_name}", 0, 0)

        # 2. 切分文档
        from src.text_splitter import split_documents, deduplicate_chunks
        chunks = split_documents(documents)
        chunks = deduplicate_chunks(chunks)

        if not chunks:
            raise ValueError("文档切分后无有效内容")

        # 3. 删除该 upload_id 的旧 chunks
        _remove_chunks_by_upload_id(upload_id)

        if progress_callback:
            progress_callback("正在生成向量", f"向量化: {original_name} ({len(chunks)} 个片段)", 0, 0)

        # 更新状态为 embedding
        update_index_status(upload_id, INDEX_STATUS_PROCESSING,
                          embedding_status=EMBEDDING_STATUS_EMBEDDING)

        # 4. 写入 Chroma
        from src.embedding_model import get_embedding_model
        from langchain_chroma import Chroma

        embedding = get_embedding_model()

        # 收集 chunk IDs
        chunk_ids = []
        valid_chunks = []
        for chunk in chunks:
            cid = chunk.metadata.get("chunk_id")
            if not cid:
                continue
            # 确保 upload 相关 metadata 存在
            chunk.metadata["upload_id"] = upload_id
            chunk.metadata["source_type"] = SOURCE_TYPE_UPLOAD
            chunk.metadata["original_name"] = original_name
            chunk.metadata["knowledge_source"] = SOURCE_TYPE_UPLOAD
            chunk.metadata["tenant_id"] = tenant_id
            chunk_ids.append(cid)
            valid_chunks.append(chunk)

        if not valid_chunks:
            raise ValueError("切分后无有效 chunk_id")

        # 使用 Chroma 添加文档
        vectorstore = Chroma(
            collection_name=COLLECTION_NAME,
            embedding_function=embedding,
            persist_directory=str(CHROMA_DIR),
        )

        vectorstore.add_documents(
            documents=valid_chunks,
            ids=chunk_ids,
        )

        if progress_callback:
            progress_callback(
                "正在更新知识库",
                f"完成: {original_name} ({len(valid_chunks)} 个片段)",
                0, 0,
            )

        # 5. 更新元数据 — embedding 完成 + indexed
        update_index_status(
            upload_id,
            INDEX_STATUS_INDEXED,
            chunk_count=len(valid_chunks),
            embedding_status=EMBEDDING_STATUS_COMPLETED,
        )

        return len(valid_chunks)

    except Exception as e:
        # 失败时回滚状态 — 标记 embedding 和 index 均失败
        try:
            update_index_status(
                upload_id,
                INDEX_STATUS_FAILED,
                error_message=_safe_str(e),
                embedding_status=EMBEDDING_STATUS_FAILED,
            )
        except Exception:
            pass
        raise

    finally:
        lock.release()


def remove_file_from_index(upload_id: str) -> dict:
    """从索引中删除指定文件的所有 chunks。

    删除顺序（确保一致性）：
    1. 从 Chroma 删除对应向量
    2. 更新 SQLite 记录（软删除）
    3. 删除磁盘文件

    任一环节失败均返回明确错误，不回滚已完成的步骤。

    Parameters
    ----------
    upload_id : str

    Returns
    -------
    dict
        {"success": bool, "deleted_count": int, "error": str | None}
    """
    result = {
        "success": False,
        "deleted_count": 0,
        "error": None,
    }

    try:
        file_record = get_file_by_id(upload_id)
        if not file_record:
            result["error"] = f"文件记录不存在: {upload_id}"
            return result

        if not file_record.get("is_active"):
            result["error"] = f"文件已被删除: {upload_id}"
            return result

        stored_name = file_record.get("stored_name", "")
        deletion_errors = []

        # ---- 步骤 1: 从 Chroma 删除对应向量 ----
        try:
            deleted = _remove_chunks_by_upload_id(upload_id)
            result["deleted_count"] = deleted
            logger.info("Chroma 向量已删除: upload_id=%s, count=%d", upload_id, deleted)
        except Exception as e:
            deletion_errors.append(f"Chroma删除失败: {_safe_str(e)}")
            logger.warning("Chroma 向量删除失败: upload_id=%s, error=%s", upload_id, e)

        # ---- 步骤 2: 更新 SQLite 记录（软删除 + embedding_status=deleted） ----
        try:
            from src.knowledge_manager import soft_delete_file
            soft_delete_file(upload_id)
            logger.info("SQLite 记录已标记删除: %s", upload_id)
        except Exception as e:
            deletion_errors.append(f"数据库删除失败: {_safe_str(e)}")
            logger.warning("SQLite 软删除失败: upload_id=%s, error=%s", upload_id, e)

        # ---- 步骤 3: 删除磁盘文件 ----
        if stored_name:
            file_path = UPLOADS_DATA_DIR / stored_name
            if file_path.is_file():
                try:
                    file_path.unlink()
                    logger.info("磁盘文件已删除: %s", file_path)
                except Exception as e:
                    deletion_errors.append(f"磁盘文件删除失败: {_safe_str(e)}")
                    logger.warning("删除磁盘文件失败: %s (%s)", file_path, e)

        if deletion_errors:
            result["error"] = "; ".join(deletion_errors)
            return result

        result["success"] = True
        return result

    except Exception as e:
        result["error"] = _safe_str(e)
        return result


def rebuild_all_indexes(
    progress_callback: callable | None = None,
) -> dict:
    """重建全部上传文件索引（仅限通过管理后台上传的文件）。

    流程:
    1. 创建 index_task 记录
    2. 从 knowledge_files 表获取所有活跃上传文件
    3. 清空 Chroma 向量库 (stage: cleaning)
    4. 重置所有文件索引状态为 pending (stage: preparing)
    5. 逐个重新索引 (stage: reparsing → embedding → writing)
    6. 完成/失败 更新 index_task

    与旧版本的区别:
    - 不再扫描 data/builtin/ 目录
    - 不再扫描 data/ 根目录
    - 不再直接从 data/uploads/ 文件系统读取
    - 改为从 knowledge_files 数据库表读取记录，确保只索引通过上传 API 管理的文件
    - 使用 index_task 表追踪重建进度

    Parameters
    ----------
    progress_callback : callable, optional
        进度回调函数，签名: callback(stage: str, detail: str, current: int, total: int)

    Returns
    -------
    dict
        {
            "success": bool,
            "total_files": int,
            "indexed": int,
            "failed": int,
            "total_chunks": int,
            "elapsed_seconds": float,
            "task_id": str | None,
            "error": str | None,
            "errors": list[str],
        }
    """
    t_start = time.perf_counter()
    task_id = None

    result = {
        "success": False,
        "total_files": 0,
        "indexed": 0,
        "failed": 0,
        "total_chunks": 0,
        "elapsed_seconds": 0.0,
        "task_id": None,
        "error": None,
        "errors": [],
    }

    try:
        from src.vector_store import reset_vector_store
        from src.knowledge_manager import (
            get_all_active_files,
            reset_all_index_status,
            SOURCE_TYPE_UPLOAD,
        )

        # ---- 1. 从数据库获取所有活跃上传文件 ----
        active_files = get_all_active_files(source_type=SOURCE_TYPE_UPLOAD)
        total = len(active_files)

        if not active_files:
            logger.info("重建索引: 没有找到活跃的上传文件，跳过")
            result["success"] = True
            result["elapsed_seconds"] = round(time.perf_counter() - t_start, 2)
            return result

        logger.info("重建索引: 发现 %d 个活跃上传文件", total)

        # ---- 创建 index_task ----
        task_id = create_index_task(total_files=total)
        result["task_id"] = task_id

        if progress_callback:
            progress_callback("准备重建", f"发现 {total} 个活跃上传文件", 0, total)
        update_index_task(task_id, status=INDEX_TASK_PREPARING, progress=0)

        # ---- 2. 清空向量库 ----
        logger.info("重建索引: 正在清空向量库...")
        if progress_callback:
            progress_callback("清空向量库", "正在删除旧索引...", 0, total)
        update_index_task(task_id, status=INDEX_TASK_CLEANING, progress=5)

        reset_vector_store()
        logger.info("重建索引: 向量库已清空")

        # ---- 3. 重置所有文件索引状态 ----
        reset_count = reset_all_index_status()
        logger.info("重建索引: 已重置 %d 条记录的状态为 pending", reset_count)
        update_index_task(task_id, status=INDEX_TASK_REPARSING, progress=10)

        # ---- 4. 逐个重新索引 ----
        result["total_files"] = total
        indexed_count = 0
        failed_count = 0
        total_chunks = 0
        errors: list[str] = []

        for i, file_record in enumerate(active_files):
            file_id = file_record["id"]
            original_name = file_record.get("original_name", "未知")

            # 计算进度: 10% (准备+清理) + 90% (逐个索引)
            progress = 10 + int((i / max(total, 1)) * 85)

            logger.info(
                "重建索引: 当前文件: %d/%d, 处理中: %s",
                i + 1, total, original_name,
            )

            if progress_callback:
                progress_callback(
                    "正在重建",
                    f"({i + 1}/{total}) {original_name}",
                    i + 1,
                    total,
                )

            update_index_task(task_id, status=INDEX_TASK_EMBEDDING,
                            progress=progress, success_count=indexed_count,
                            failed_count=failed_count)

            try:
                chunk_count = index_single_file(file_id, progress_callback)
                indexed_count += 1
                total_chunks += chunk_count
                update_index_task(task_id, success_count=indexed_count,
                                total_chunks=total_chunks)
                logger.info(
                    "重建索引: [%d/%d] 完成: %s (%d chunks)",
                    i + 1, total, original_name, chunk_count,
                )
            except Exception as e:
                failed_count += 1
                error_msg = str(e).split("\n")[0][:200]
                errors.append(f"{original_name}: {error_msg}")
                update_index_task(task_id, failed_count=failed_count)
                logger.warning(
                    "重建索引: [%d/%d] 失败: %s -- %s",
                    i + 1, total, original_name, error_msg,
                )
                # index_single_file 已将状态设为 failed，无需额外处理

        result["success"] = failed_count == 0
        result["indexed"] = indexed_count
        result["failed"] = failed_count
        result["total_chunks"] = total_chunks
        result["errors"] = errors
        result["elapsed_seconds"] = round(time.perf_counter() - t_start, 2)

        # ---- 完成 ----
        update_index_task(
            task_id,
            status=INDEX_TASK_COMPLETED if result["success"] else INDEX_TASK_FAILED,
            progress=100,
            success_count=indexed_count,
            failed_count=failed_count,
            total_chunks=total_chunks,
        )

        logger.info(
            "重建索引完成: 成功 %d/%d, 失败 %d, 总 chunks %d, 耗时 %.2fs",
            indexed_count, total, failed_count, total_chunks,
            result["elapsed_seconds"],
        )

        if progress_callback:
            progress_callback(
                "完成",
                f"重建完成: 成功 {indexed_count}/{total}, "
                f"{total_chunks} chunks, 耗时 {result['elapsed_seconds']:.1f}s",
                total, total,
            )

        return result

    except Exception as e:
        result["error"] = str(e).split("\n")[0][:200]
        logger.error("重建索引异常: %s", result["error"], exc_info=True)
        if task_id:
            try:
                update_index_task(task_id, status=INDEX_TASK_FAILED,
                                error_message=result["error"])
            except Exception:
                pass
        return result


def get_index_statistics() -> dict:
    """获取索引统计信息。

    必须使用与 RAG 完全相同的 get_chroma_client() 单例，
    禁止创建新的 PersistentClient（会导致 SQLite 文件锁冲突且读取不到数据）。

    Returns
    -------
    dict
    """
    from src.vector_store import get_chroma_client

    try:
        client = get_chroma_client()
        try:
            collection = client.get_collection(COLLECTION_NAME)
            total_count = collection.count()
        except Exception as e:
            err_msg = str(e).lower()
            if "does not exist" in err_msg or "not found" in err_msg:
                return {
                    "chroma_status": "not_found",
                    "total_vectors": 0,
                }
            return {
                "chroma_status": "error",
                "total_vectors": 0,
                "error": _safe_str(e),
            }

        return {
            "chroma_status": "ok",
            "total_vectors": total_count,
        }
    except Exception as e:
        return {
            "chroma_status": "error",
            "total_vectors": 0,
            "error": _safe_str(e),
        }


def refresh_chroma_client() -> None:
    """刷新 Chroma 客户端缓存，使新索引的数据在问答中可见。

    必须使用 get_chroma_client() 单例，禁止创建新的 PersistentClient。
    """
    from src.vector_store import get_chroma_client

    try:
        client = get_chroma_client()
        # 尝试获取 collection 以触发刷新
        try:
            _ = client.get_collection(COLLECTION_NAME)
        except Exception:
            pass
        logger.info("Chroma 客户端缓存已刷新")
    except Exception as e:
        logger.warning("刷新 Chroma 客户端缓存失败: %s", e)


# ---------------------------------------------------------------------------
# 内部辅助
# ---------------------------------------------------------------------------


def _remove_chunks_by_upload_id(upload_id: str) -> int:
    """从 Chroma 中删除属于指定 upload_id 的所有 chunks。

    使用 Chroma 的 where 过滤实现精确删除，
    不通过删除整个 collection 来实现。

    必须使用 get_chroma_client() 单例。

    Parameters
    ----------
    upload_id : str

    Returns
    -------
    int
        删除的 chunk 数量
    """
    from src.vector_store import get_chroma_client

    try:
        client = get_chroma_client()
        try:
            collection = client.get_collection(COLLECTION_NAME)

            # 先查询属于该 upload_id 的所有记录
            existing = collection.get(
                where={"upload_id": upload_id},
            )
            existing_ids = existing.get("ids", [])

            if existing_ids:
                collection.delete(ids=existing_ids)
                logger.info(
                    "已从索引中删除 %d 条记录 (upload_id=%s)",
                    len(existing_ids), upload_id,
                )
                return len(existing_ids)

            return 0
        except Exception as e:
            logger.warning("删除索引记录失败: %s", e)
            return 0
    except Exception as e:
        logger.warning("连接 Chroma 失败: %s", e)
        return 0


def _safe_str(exc: Exception) -> str:
    """从异常中提取安全摘要。"""
    return str(exc).split("\n")[0][:200]
