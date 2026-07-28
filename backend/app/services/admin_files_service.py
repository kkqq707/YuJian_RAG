"""管理员知识库文件管理服务

提供:
- 文件列表查询（含版本信息）
- 文件上传（自动版本管理 → DocumentLoader → TextSplitter → Embedding → Chroma）
- 文件删除（SQLite → Chroma → 磁盘文件）
- 文件详情（含版本历史）
- 文件内容预览（TXT/MD/PDF/DOCX，分页加载）
- 版本管理（删除版本、恢复版本）
- 索引重建
- 索引状态查询

安全:
- 不上传时调用 DeepSeek
- 不修改核心 RAG 服务
- 复用 src/index_manager 和 src/knowledge_manager
"""

from __future__ import annotations

import asyncio
import logging
import sys
import threading
import time
import uuid
from pathlib import Path
from typing import Optional

from fastapi import UploadFile

from backend.app.config import get_settings
from backend.app.schemas.document_task import (
    RebuildAcceptedResponse,
    UploadAcceptedResponse,
)
from backend.app.services.document_task_runtime import get_document_task_runtime
from backend.app.services.document_task_service import DocumentTaskService
from backend.app.services.file_upload import (
    stream_upload_to_disk,
    check_duplicate_file,
    validate_extension,
    validate_safe_filename,
    ERR_FILE_TOO_LARGE,
    ERR_UNSUPPORTED_FILE_TYPE,
    ERR_EMPTY_FILE,
    ERR_INVALID_FILE_CONTENT,
    ERR_DUPLICATE_DOCUMENT,
    ERR_UPLOAD_BUSY,
)
from backend.app.vector_store_runtime import (
    get_vector_store_runtime,
    VectorStoreBusyError,
    DuplicateOperationError,
)

logger = logging.getLogger(__name__)


class AdminFilesService:
    """管理员知识库文件管理服务。

    Phase 7: 添加 Chroma 写锁保护。
    """

    # Phase 7: 类级别重建标志和锁
    _rebuild_lock = threading.Lock()
    _rebuild_in_progress: bool = False

    def __init__(self):
        self.settings = get_settings()
        self._ensure_src_path()

    # ------------------------------------------------------------------
    # Phase 8: 异步上传（流式写入 + 后台索引）
    # ------------------------------------------------------------------

    async def upload_files_async(
        self, files: list[UploadFile], created_by: str = "admin"
    ) -> dict:
        """流式上传文件并创建后台索引任务（Phase 8）。

        流程:
        1. 流式分块写入磁盘
        2. 安全校验
        3. SHA-256 校验
        4. 创建 Document 记录
        5. 创建 DocumentTask
        6. 返回 202 Accepted

        Returns dict 包含 file 结果和 task_id 信息。
        """
        from src.config import UPLOADS_DATA_DIR
        UPLOADS_DATA_DIR.mkdir(parents=True, exist_ok=True)

        runtime = get_document_task_runtime()
        task_service = DocumentTaskService()

        results = []
        succeeded = 0
        failed = 0
        skipped = 0

        for file in files:
            # Phase 8: 流式上传
            upload_result = await stream_upload_to_disk(
                file, UPLOADS_DATA_DIR,
                upload_semaphore=runtime.upload_semaphore,
            )

            if not upload_result["success"]:
                failed += 1
                results.append({
                    "filename": file.filename or "unknown",
                    "success": False,
                    "document_id": None,
                    "task_id": None,
                    "error": upload_result["error"],
                    "error_code": upload_result.get("error_code"),
                    "skipped": False,
                })
                continue

            # 重复检测
            existing = check_duplicate_file(
                upload_result["file_hash"],
                upload_result["file_size"],
                UPLOADS_DATA_DIR,
            )
            if existing:
                skipped += 1
                results.append({
                    "filename": file.filename or "unknown",
                    "success": True,
                    "document_id": existing["id"],
                    "task_id": None,
                    "error": "文件已存在，无需重新上传",
                    "error_code": ERR_DUPLICATE_DOCUMENT,
                    "skipped": True,
                })
                # 清理重复文件
                dup_path = UPLOADS_DATA_DIR / upload_result["stored_name"]
                if dup_path.exists():
                    try:
                        dup_path.unlink()
                    except Exception:
                        pass
                continue

            # 创建 Document 记录
            try:
                from src.knowledge_manager import (
                    init_database, add_file_record,
                )
                init_database()
                doc_id = add_file_record(
                    original_name=upload_result["original_name"],
                    stored_name=upload_result["stored_name"],
                    stored_path=upload_result["stored_path"],
                    file_type=upload_result["file_type"],
                    file_size=upload_result["file_size"],
                    file_hash=upload_result["file_hash"],
                    source_type="upload",
                    tenant_id="default",
                )
            except ValueError as e:
                failed += 1
                # 清理文件
                dup_path = UPLOADS_DATA_DIR / upload_result["stored_name"]
                if dup_path.exists():
                    try:
                        dup_path.unlink()
                    except Exception:
                        pass
                results.append({
                    "filename": file.filename or "unknown",
                    "success": False,
                    "document_id": None,
                    "task_id": None,
                    "error": str(e)[:300],
                    "error_code": ERR_DUPLICATE_DOCUMENT,
                    "skipped": False,
                })
                continue

            # 创建后台索引任务
            try:
                task = task_service.create_index_task(
                    document_id=doc_id,
                    task_type="index_document",
                    created_by=created_by,
                )
                task_id = task.id
            except ValueError as e:
                # 队列满 — 文档已保存但任务创建失败
                logger.warning("索引任务创建失败: doc=%s — %s", doc_id, str(e)[:200])
                task_id = None

            succeeded += 1
            results.append({
                "filename": upload_result["original_name"],
                "success": True,
                "document_id": doc_id,
                "task_id": task_id,
                "error": None,
                "skipped": False,
            })

        runtime.metrics.record_upload()
        return {
            "success": True,
            "message": f"上传完成: 成功 {succeeded} 个, 失败 {failed} 个"
            + (f", 跳过 {skipped} 个（已存在）" if skipped > 0 else ""),
            "total": len(files),
            "succeeded": succeeded,
            "failed": failed,
            "skipped": skipped,
            "results": results,
        }

    # ------------------------------------------------------------------
    # Phase 8: 异步重建索引
    # ------------------------------------------------------------------

    async def rebuild_index_async(self, created_by: str = "admin") -> dict:
        """创建后台重建索引任务（Phase 8）。"""
        # 检查重复
        if AdminFilesService._rebuild_in_progress:
            raise DuplicateOperationError("索引重建正在进行中，请稍后再试")

        task_service = DocumentTaskService()
        task = task_service.create_rebuild_task(created_by=created_by)

        return RebuildAcceptedResponse(
            success=True,
            message="索引重建任务已创建，将在后台执行",
            task_id=task.id,
            status="pending",
        ).model_dump()

    # ------------------------------------------------------------------
    # Phase 8: 异步单文件索引
    # ------------------------------------------------------------------

    async def index_single_file_async(
        self, file_id: str, created_by: str = "admin"
    ) -> dict:
        """为单个文件创建后台索引任务（Phase 8）。"""
        task_service = DocumentTaskService()
        task = task_service.create_index_task(
            document_id=file_id,
            task_type="index_document",
            created_by=created_by,
        )
        return UploadAcceptedResponse(
            success=True,
            message="索引任务已创建",
            document_id=file_id,
            task_id=task.id,
            status="pending",
        ).model_dump()

    # ------------------------------------------------------------------
    # 内部
    # ------------------------------------------------------------------

    @staticmethod
    def _ensure_src_path():
        """确保项目根在 sys.path 中。"""
        project_root = get_settings().PROJECT_ROOT
        if str(project_root) not in sys.path:
            sys.path.insert(0, str(project_root))

    # ------------------------------------------------------------------
    # 文件列表
    # ------------------------------------------------------------------

    def list_files(self, source_type: Optional[str] = None) -> dict:
        """获取知识库文件列表（含版本信息）。

        Parameters
        ----------
        source_type : str, optional
            过滤来源类型: 'builtin' | 'upload'

        Returns
        -------
        dict
        """
        from src.knowledge_manager import init_database, get_all_active_files

        # 确保数据库和表存在（幂等操作）
        try:
            init_database()
        except Exception as db_err:
            logger.warning("初始化知识库数据库失败: %s", str(db_err)[:200])
            return {
                "success": True,
                "total": 0,
                "files": [],
            }

        try:
            files = get_all_active_files(source_type=source_type)
            return {
                "success": True,
                "total": len(files),
                "files": files,
            }
        except Exception as e:
            logger.warning("查询文件列表失败: %s", str(e)[:200])
            return {
                "success": True,
                "total": 0,
                "files": [],
            }

    # ------------------------------------------------------------------
    # 文件上传（带版本管理）
    # ------------------------------------------------------------------

    async def upload_files(self, files: list[UploadFile]) -> dict:
        """上传并自动索引知识库文件（带版本管理）。

        流程:
        1. 安全校验每个文件
        2. 计算 SHA-256 哈希
        3. 查重：相同哈希 → 提示已存在
        4. 查同名：哈希不同 → 生成新版本 (v2, v3...)
        5. 保存到磁盘
        6. 逐个索引

        Parameters
        ----------
        files : list[UploadFile]
            上传的文件列表

        Returns
        -------
        dict
        """
        from src.config import UPLOADS_DATA_DIR

        UPLOADS_DATA_DIR.mkdir(parents=True, exist_ok=True)

        results = []
        succeeded = 0
        failed = 0
        skipped = 0

        for file in files:
            result = await self._process_single_file_v2(file, UPLOADS_DATA_DIR)
            if result.get("skipped"):
                skipped += 1
            if result["success"]:
                succeeded += 1
            else:
                failed += 1
            results.append(result)

        return {
            "success": True,
            "message": f"上传完成: 成功 {succeeded} 个, 失败 {failed} 个"
            + (f", 跳过 {skipped} 个（已存在）" if skipped > 0 else ""),
            "total": len(files),
            "succeeded": succeeded,
            "failed": failed,
            "skipped": skipped,
            "results": results,
        }

    async def _process_single_file_v2(self, file: UploadFile, upload_dir: Path) -> dict:
        """处理单个上传文件（带版本管理）。"""
        from src.file_validator import (
            validate_upload,
            generate_stored_name,
        )
        from src.knowledge_manager import (
            add_file_record,
            init_database,
            get_file_by_hash,
            get_files_by_original_name,
            get_latest_version_number,
            create_file_version,
            update_file_version_info,
            add_operation_log,
            CHANGE_TYPE_CREATE,
            CHANGE_TYPE_UPDATE,
        )
        from src.index_manager import index_single_file

        filename = file.filename or "unknown"
        result = {
            "filename": filename,
            "success": False,
            "file_id": None,
            "version": None,
            "error": None,
            "skipped": False,
        }

        try:
            # 1. 读取文件内容
            content = await file.read()
            file_size = len(content)

            # 2. 安全校验
            validation = validate_upload(filename, content, file_size)
            if not validation["valid"]:
                result["error"] = validation["error"]
                add_operation_log(
                    user_id="admin",
                    operation="upload_file",
                    target=filename,
                    result="failed",
                )
                return result

            file_hash = validation["file_hash"]

            # 3. 查重：相同哈希 → 已存在
            existing = get_file_by_hash(file_hash)
            if existing and existing.get("is_active"):
                result["success"] = True
                result["file_id"] = existing["id"]
                result["version"] = existing.get("current_version", "v1")
                result["skipped"] = True
                result["error"] = "该文件已存在，无需重新索引"
                logger.info("文件已存在，跳过: %s (hash=%s)", filename, file_hash[:16])
                return result

            # 4. 初始化数据库
            init_database()

            # 5. 查同名文件 → 版本管理
            same_name_files = get_files_by_original_name(filename)
            is_new_version = len(same_name_files) > 0

            if is_new_version:
                # 同名文件存在 → 创建新版本
                latest_num = get_latest_version_number(same_name_files[0]["id"])
                new_version = f"v{latest_num + 1}"
                result["version"] = new_version

                # 保存新版本文件
                upload_id = same_name_files[0]["id"]
                safe_name = validation["safe_filename"]
                stored_name = generate_stored_name(str(uuid.uuid4()), safe_name)
                stored_path = upload_dir / stored_name
                stored_path.write_bytes(content)

                # 创建版本记录
                create_file_version(
                    file_id=upload_id,
                    version=new_version,
                    file_hash=file_hash,
                    file_size=file_size,
                    operator="admin",
                    change_type=CHANGE_TYPE_UPDATE,
                    stored_name=stored_name,
                )

                # 更新文件主记录的版本信息
                update_file_version_info(
                    file_id=upload_id,
                    current_version=new_version,
                    file_hash=file_hash,
                    file_size=file_size,
                )

                # 删除旧索引并重新索引新文件
                await self._reindex_file_with_new_version(
                    upload_id, stored_path, file_type=validation["file_type"]
                )

                result["success"] = True
                result["file_id"] = upload_id

                add_operation_log(
                    user_id="admin",
                    operation="update_version",
                    target=f"{filename} → {new_version}",
                    result="success",
                )
                logger.info(
                    "文件版本更新: %s → %s (id=%s, hash=%s)",
                    filename, new_version, upload_id, file_hash[:16],
                )
            else:
                # 新文件 → 创建初版 v1
                upload_id = str(uuid.uuid4())
                safe_name = validation["safe_filename"]
                stored_name = generate_stored_name(upload_id, safe_name)
                stored_path = upload_dir / stored_name
                stored_path.write_bytes(content)

                # 添加元数据记录
                file_id = add_file_record(
                    original_name=filename,
                    stored_name=stored_name,
                    stored_path=str(stored_path),
                    file_type=validation["file_type"],
                    file_size=file_size,
                    file_hash=file_hash,
                    source_type="upload",
                    tenant_id="default",
                )

                # 创建初始版本记录 v1
                create_file_version(
                    file_id=file_id,
                    version="v1",
                    file_hash=file_hash,
                    file_size=file_size,
                    operator="admin",
                    change_type=CHANGE_TYPE_CREATE,
                    stored_name=stored_name,
                )

                result["success"] = True
                result["file_id"] = file_id
                result["version"] = "v1"

                add_operation_log(
                    user_id="admin",
                    operation="upload_file",
                    target=filename,
                    result="success",
                )

                # 自动索引
                try:
                    from src.knowledge_manager import update_index_status
                    update_index_status(file_id, "pending", embedding_status="pending")
                    chunk_count = index_single_file(file_id)
                    result["index_status"] = "indexed"
                    result["chunk_count"] = chunk_count
                    logger.info(
                        "文件自动索引成功: %s → %d chunks (id=%s)",
                        filename, chunk_count, file_id,
                    )
                except Exception as index_err:
                    index_msg = str(index_err).split("\n")[0][:200]
                    logger.warning(
                        "文件自动索引失败(上传不受影响): %s — %s (id=%s)",
                        filename, index_msg, file_id,
                    )
                    result["index_error"] = index_msg

        except Exception as e:
            result["error"] = str(e).split("\n")[0][:200]
            logger.warning("文件上传失败: %s — %s", filename, result["error"])
            try:
                add_operation_log(
                    user_id="admin",
                    operation="upload_file",
                    target=filename,
                    result="failed",
                )
            except Exception:
                pass

        return result

    async def _reindex_file_with_new_version(
        self, file_id: str, new_stored_path: Path, file_type: str
    ) -> None:
        """为新版本文件重建索引（Phase 7: 带写锁保护）。"""
        from src.knowledge_manager import (
            update_index_status,
            update_file_preview_status,
        )
        from src.index_manager import index_single_file, _remove_chunks_by_upload_id

        runtime = get_vector_store_runtime()
        try:
            await asyncio.wait_for(runtime.write_lock.acquire(), timeout=30.0)
        except asyncio.TimeoutError:
            runtime.metrics.record_write_timeout()
            raise VectorStoreBusyError("知识库正在处理其他写操作，请稍后重试")

        try:
            # 删除旧索引
            _remove_chunks_by_upload_id(file_id)

            # 更新存储路径（暂时指向新文件用于索引）
            from src.knowledge_manager import _get_connection
            conn = _get_connection()
            try:
                conn.execute(
                    "UPDATE knowledge_files SET stored_path = ?, stored_name = ? WHERE id = ?",
                    (str(new_stored_path), new_stored_path.name, file_id),
                )
                conn.commit()
            finally:
                conn.close()

            # 重置状态并重新索引
            update_index_status(file_id, "pending", embedding_status="pending")
            chunk_count = index_single_file(file_id)
            update_file_preview_status(file_id, True)

            logger.info(
                "新版本索引成功: file_id=%s, chunks=%d", file_id, chunk_count,
            )
        except Exception as e:
            logger.warning("新版本索引失败: file_id=%s — %s", file_id, str(e)[:200])
        finally:
            runtime.write_lock.release()

    # ------------------------------------------------------------------
    # 文件详情
    # ------------------------------------------------------------------

    def get_file_detail(self, file_id: str) -> dict:
        """获取文件详情（含版本历史）。

        Parameters
        ----------
        file_id : str

        Returns
        -------
        dict
        """
        from src.knowledge_manager import (
            get_file_by_id,
            get_file_versions,
        )

        file_record = get_file_by_id(file_id)
        if not file_record:
            return {"success": False, "message": "文件不存在"}

        versions = get_file_versions(file_id)

        # 获取 vector 数量（从 Chroma）
        vector_count = 0
        try:
            from src.vector_store import get_chroma_client
            from src.config import COLLECTION_NAME
            client = get_chroma_client()
            try:
                collection = client.get_collection(COLLECTION_NAME)
            except Exception:
                # Collection 不存在时使用 get_or_create
                collection = client.create_collection(
                    name=COLLECTION_NAME,
                    metadata={"hnsw:space": "cosine"},
                )
            existing = collection.get(where={"upload_id": file_id})
            vector_count = len(existing.get("ids", []))
        except Exception:
            pass

        return {
            "success": True,
            "file": {
                **file_record,
                "versions": versions,
                "vector_count": vector_count,
            },
        }

    # ------------------------------------------------------------------
    # 文件内容预览
    # ------------------------------------------------------------------

    def get_file_content(
        self,
        file_id: str,
        page: int = 1,
        page_size: int = 10000,
    ) -> dict:
        """获取文件内容预览（分页）。

        支持格式: TXT, MD, PDF, DOCX

        Parameters
        ----------
        file_id : str
        page : int
            页码（从 1 开始）
        page_size : int
            每页字符数，默认 10000

        Returns
        -------
        dict
        """
        from src.knowledge_manager import get_file_by_id

        file_record = get_file_by_id(file_id)
        if not file_record:
            return {"success": False, "message": "文件不存在"}

        stored_name = file_record.get("stored_name", "")
        file_type = file_record.get("file_type", "").lower()
        from src.config import UPLOADS_DATA_DIR

        file_path = UPLOADS_DATA_DIR / stored_name
        if not file_path.is_file():
            return {"success": False, "message": "文件在磁盘上不存在，可能已被清理"}

        try:
            full_content = self._extract_text(file_path, file_type)
            total_chars = len(full_content)
            total_pages = max(1, (total_chars + page_size - 1) // page_size)

            start = (page - 1) * page_size
            end = start + page_size
            page_content = full_content[start:end]

            # 获取 chunks 信息
            chunks = []
            try:
                from src.vector_store import get_chroma_client
                from src.config import COLLECTION_NAME
                client = get_chroma_client()
                try:
                    collection = client.get_collection(COLLECTION_NAME)
                except Exception:
                    collection = client.create_collection(
                        name=COLLECTION_NAME,
                        metadata={"hnsw:space": "cosine"},
                    )
                existing = collection.get(
                    where={"upload_id": file_id},
                    include=["documents"],
                )
                for doc in existing.get("documents", [])[:5]:
                    chunks.append(doc[:200] + "..." if len(doc) > 200 else doc)
            except Exception:
                pass

            return {
                "success": True,
                "content": page_content,
                "page": page,
                "page_size": page_size,
                "total_chars": total_chars,
                "total_pages": total_pages,
                "file_type": file_type,
                "chunks_preview": chunks,
            }
        except Exception as e:
            return {"success": False, "message": f"文件读取失败: {str(e)[:200]}"}

    @staticmethod
    def _extract_text(file_path: Path, file_type: str) -> str:
        """从文件提取纯文本内容。

        Parameters
        ----------
        file_path : Path
        file_type : str

        Returns
        -------
        str
        """
        if file_type in (".txt", ".md", "txt", "md"):
            # 尝试多种编码
            raw = file_path.read_bytes()
            for enc in ["utf-8", "utf-8-sig", "gb18030", "gbk"]:
                try:
                    return raw.decode(enc)
                except (UnicodeDecodeError, LookupError):
                    continue
            return raw.decode("utf-8", errors="replace")

        elif file_type in (".pdf", "pdf"):
            from pypdf import PdfReader
            reader = PdfReader(str(file_path))
            pages = []
            for page_obj in reader.pages:
                try:
                    text = page_obj.extract_text()
                    if text:
                        pages.append(text)
                except Exception:
                    pass
            return "\n\n".join(pages)

        elif file_type in (".docx", "docx"):
            import docx as _docx
            doc = _docx.Document(str(file_path))
            paragraphs = [p.text for p in doc.paragraphs if p.text and p.text.strip()]
            return "\n".join(paragraphs)

        else:
            return "[不支持预览的文件类型]"

    # ------------------------------------------------------------------
    # 版本管理
    # ------------------------------------------------------------------

    def delete_version(self, file_id: str, version_id: str) -> dict:
        """删除指定版本记录。

        Parameters
        ----------
        file_id : str
        version_id : str

        Returns
        -------
        dict
        """
        from src.knowledge_manager import (
            get_file_by_id,
            get_file_versions,
            get_version_by_id,
            delete_version_record,
            update_file_version_info,
            add_operation_log,
        )

        file_record = get_file_by_id(file_id)
        if not file_record:
            return {"success": False, "message": "文件不存在"}

        version = get_version_by_id(version_id)
        if not version:
            return {"success": False, "message": "版本记录不存在"}

        if version["file_id"] != file_id:
            return {"success": False, "message": "版本不属于该文件"}

        versions = get_file_versions(file_id)
        if len(versions) <= 1:
            return {"success": False, "message": "至少保留一个版本，无法删除"}

        # 如果删除的是当前版本，回退到上一个版本
        current_version = file_record.get("current_version", "v1")
        is_current = version["version"] == current_version

        # 删除版本记录
        delete_version_record(version_id)

        if is_current:
            # 回退到最新剩余版本
            remaining = get_file_versions(file_id)
            if remaining:
                new_current = remaining[0]["version"]
                update_file_version_info(file_id, new_current)
                logger.info(
                    "版本回退: %s 从 %s 回退到 %s",
                    file_record.get("original_name", ""), current_version, new_current,
                )

        add_operation_log(
            user_id="admin",
            operation="delete_version",
            target=f"{file_record.get('original_name', '')} {version['version']}",
            result="success",
        )

        return {
            "success": True,
            "message": f"版本 {version['version']} 已删除",
            "was_current": is_current,
        }

    def restore_version(self, file_id: str, version_id: str) -> dict:
        """恢复指定版本。

        Parameters
        ----------
        file_id : str
        version_id : str

        Returns
        -------
        dict
        """
        from src.knowledge_manager import (
            get_file_by_id,
            get_version_by_id,
            update_file_version_info,
            add_operation_log,
            CHANGE_TYPE_ROLLBACK,
        )
        from src.index_manager import _remove_chunks_by_upload_id

        file_record = get_file_by_id(file_id)
        if not file_record:
            return {"success": False, "message": "文件不存在"}

        version = get_version_by_id(version_id)
        if not version:
            return {"success": False, "message": "版本记录不存在"}

        if version["file_id"] != file_id:
            return {"success": False, "message": "版本不属于该文件"}

        # 更新当前版本信息
        target_version = version["version"]
        update_file_version_info(
            file_id,
            current_version=target_version,
            file_hash=version["file_hash"],
            file_size=version["file_size"],
        )

        add_operation_log(
            user_id="admin",
            operation="restore_version",
            target=f"{file_record.get('original_name', '')} → {target_version}",
            result="success",
        )

        logger.info(
            "版本恢复: %s → %s",
            file_record.get("original_name", ""), target_version,
        )

        return {
            "success": True,
            "message": f"已恢复到版本 {target_version}",
            "current_version": target_version,
        }

    # ------------------------------------------------------------------
    # 单文件索引
    # ------------------------------------------------------------------

    async def index_single_file(self, file_id: str) -> dict:
        """为单个文件建立或重建索引（Phase 7: 带写锁保护）。

        Parameters
        ----------
        file_id : str
            文件记录 ID

        Returns
        -------
        dict
        """
        from src.index_manager import index_single_file as do_index
        from src.knowledge_manager import update_file_preview_status, add_operation_log

        runtime = get_vector_store_runtime()
        try:
            await asyncio.wait_for(runtime.write_lock.acquire(), timeout=30.0)
        except asyncio.TimeoutError:
            runtime.metrics.record_write_timeout()
            raise VectorStoreBusyError("知识库正在处理其他写操作，请稍后重试")

        try:
            chunk_count = do_index(file_id)
            update_file_preview_status(file_id, True)
            add_operation_log(
                user_id="admin",
                operation="reindex",
                target=f"file_id={file_id}",
                result="success",
            )
            logger.info("单文件索引成功: %s → %d chunks", file_id, chunk_count)
            return {
                "success": True,
                "message": f"索引完成，共 {chunk_count} 个片段",
                "chunk_count": chunk_count,
            }
        except Exception as e:
            error_msg = str(e).split("\n")[0][:200]
            logger.warning("单文件索引失败: %s — %s", file_id, error_msg)
            add_operation_log(
                user_id="admin",
                operation="reindex",
                target=f"file_id={file_id}",
                result="failed",
            )
            return {
                "success": False,
                "message": error_msg,
                "chunk_count": 0,
            }
        finally:
            runtime.write_lock.release()

    # ------------------------------------------------------------------
    # 文件删除
    # ------------------------------------------------------------------

    async def delete_file(self, file_id: str) -> dict:
        """删除知识库文件（Phase 7: 带写锁保护）。

        流程:
        1. 从 Chroma 删除对应 chunks
        2. 更新 SQLite 记录（软删除）
        3. 删除磁盘文件
        4. 刷新索引统计

        Parameters
        ----------
        file_id : str
            文件记录 ID

        Returns
        -------
        dict
        """
        from src.index_manager import remove_file_from_index
        from src.knowledge_manager import add_operation_log, get_file_by_id

        file_record = get_file_by_id(file_id)
        original_name = file_record.get("original_name", "未知") if file_record else "未知"

        runtime = get_vector_store_runtime()
        try:
            await asyncio.wait_for(runtime.write_lock.acquire(), timeout=30.0)
        except asyncio.TimeoutError:
            runtime.metrics.record_write_timeout()
            raise VectorStoreBusyError("知识库正在处理其他写操作，请稍后重试")

        try:
            result = remove_file_from_index(file_id)

            if result["success"]:
                add_operation_log(
                    user_id="admin",
                    operation="delete_file",
                    target=original_name,
                    result="success",
                )
                logger.info("文件删除成功: %s, 删除 %d chunks", file_id, result["deleted_count"])
                return {
                    "success": True,
                    "message": "文件已删除",
                    "file_id": file_id,
                    "deleted_chunks": result["deleted_count"],
                }
            else:
                error_msg = result.get("error", "删除失败")
                logger.warning("文件删除失败: %s — %s", file_id, error_msg)
                return {
                    "success": False,
                    "message": error_msg,
                    "file_id": file_id,
                    "deleted_chunks": 0,
                }
        finally:
            runtime.write_lock.release()

    # ------------------------------------------------------------------
    # 重建索引
    # ------------------------------------------------------------------

    async def rebuild_index(self) -> dict:
        """重建全部上传文件索引（Phase 7: 带全局写锁和重复重建保护）。

        流程:
        1. 检查是否有重建正在进行（重复重建返回 409）
        2. 获取全局写锁
        3. 从数据库获取活跃上传文件列表
        4. 清空 Chroma 向量库
        5. 重置所有状态为 pending
        6. 逐个重新索引

        进度信息通过服务端日志输出。

        Returns
        -------
        dict
        """
        from src.index_manager import rebuild_all_indexes

        # Phase 7: 检查是否有重建正在进行
        if AdminFilesService._rebuild_in_progress:
            raise DuplicateOperationError("索引重建正在进行中，请稍后再试")

        def log_progress(stage: str, detail: str, current: int, total: int):
            """将索引进度写入服务端日志。"""
            logger.info("索引重建进度 [%s]: %s (%s/%s)", stage, detail, current, total)

        logger.info("管理员触发索引重建...")
        t0 = time.time()

        # Phase 7: 获取全局写锁
        runtime = get_vector_store_runtime()
        try:
            await asyncio.wait_for(runtime.write_lock.acquire(), timeout=30.0)
        except asyncio.TimeoutError:
            runtime.metrics.record_write_timeout()
            raise VectorStoreBusyError("知识库正在处理其他写操作，请稍后重试")

        # Phase 7: 设置重建标志 + 获取重建锁
        with AdminFilesService._rebuild_lock:
            if AdminFilesService._rebuild_in_progress:
                raise DuplicateOperationError("索引重建正在进行中，请稍后再试")
            AdminFilesService._rebuild_in_progress = True

        try:
            # Phase 7: 记录向量库写操作指标
            try:
                runtime.metrics.vector_write_active = 1
            except Exception:
                pass

            result = rebuild_all_indexes(progress_callback=log_progress)

            if result["success"]:
                logger.info(
                    "索引重建完成: %d/%d 文件成功, %d chunks, 耗时 %.2fs",
                    result.get("indexed", 0),
                    result.get("total_files", 0),
                    result.get("total_chunks", 0),
                    result.get("elapsed_seconds", 0),
                )
                return {
                    "success": True,
                    "message": (
                        f"索引重建完成，共处理 {result['total_files']} 个文件，"
                        f"成功 {result['indexed']} 个，"
                        f"共 {result['total_chunks']} 个片段"
                    ),
                    "total_files": result.get("total_files", 0),
                    "indexed": result.get("indexed", 0),
                    "failed": result.get("failed", 0),
                    "total_chunks": result.get("total_chunks", 0),
                    "elapsed_seconds": result.get("elapsed_seconds", 0.0),
                    "task_id": result.get("task_id"),
                    "errors": result.get("errors", []),
                }
            else:
                error_msg = result.get("error", "重建失败")
                logger.warning("索引重建失败: %s", error_msg)
                return {
                    "success": False,
                    "message": error_msg,
                    "total_files": result.get("total_files", 0),
                    "indexed": result.get("indexed", 0),
                    "failed": result.get("failed", 0),
                    "total_chunks": result.get("total_chunks", 0),
                    "elapsed_seconds": result.get("elapsed_seconds", 0.0),
                    "task_id": result.get("task_id"),
                    "errors": result.get("errors", []),
                    "error": error_msg,
                }
        finally:
            AdminFilesService._rebuild_in_progress = False
            try:
                runtime.metrics.vector_write_active = 0
                runtime.metrics.record_write()
            except Exception:
                pass
            runtime.write_lock.release()

    # ------------------------------------------------------------------
    # 索引状态
    # ------------------------------------------------------------------

    def get_index_status(self) -> dict:
        """获取索引状态和统计信息。

        Returns
        -------
        dict
        """
        from src.index_manager import get_index_statistics
        from src.knowledge_manager import init_database, get_statistics, get_all_active_files
        from src.config import EMBEDDING_MODEL_NAME, COLLECTION_NAME

        # 确保数据库和表存在（幂等操作）
        try:
            init_database()
        except Exception:
            pass

        try:
            index_stats = get_index_statistics()
        except Exception:
            index_stats = {"total_vectors": 0, "chroma_status": "error"}

        try:
            kb_stats = get_statistics()
        except Exception:
            kb_stats = {"indexed_files": 0, "total_chunks": 0, "last_update_time": None}

        # 获取待索引文件数
        pending_files = [
            f for f in get_all_active_files(source_type="upload")
            if f.get("index_status") in ("pending", "failed")
        ]

        # 一致性检查
        db_indexed = kb_stats.get("indexed_files", 0)
        chroma_vectors = index_stats.get("total_vectors", 0)
        db_chunks = kb_stats.get("total_chunks", 0)

        if db_indexed > 0 and chroma_vectors == 0:
            consistency_ok = False
            consistency_note = "数据库显示已索引但 Chroma 为空，需要重建索引"
        elif db_indexed == 0 and chroma_vectors > 0:
            consistency_ok = False
            consistency_note = "Chroma 有向量但数据库无记录，状态不一致"
        elif db_indexed == 0 and chroma_vectors == 0:
            consistency_ok = True
            consistency_note = "无索引数据（正常状态）"
        else:
            consistency_ok = True
            consistency_note = "数据库与 Chroma 状态一致"

        return {
            "success": True,
            "chroma_status": index_stats.get("chroma_status", "unknown"),
            "total_vectors": chroma_vectors,
            "indexed_files": db_indexed,
            "pending_files": len(pending_files),
            "total_chunks": db_chunks,
            "last_update_time": kb_stats.get("last_update_time"),
            "embedding_model": EMBEDDING_MODEL_NAME,
            "chroma_collection": COLLECTION_NAME,
            "consistency_ok": consistency_ok,
            "consistency_note": consistency_note,
        }

    # ------------------------------------------------------------------
    # 操作日志
    # ------------------------------------------------------------------

    def get_operation_logs(self, limit: int = 50) -> dict:
        """获取操作日志。

        Parameters
        ----------
        limit : int

        Returns
        -------
        dict
        """
        from src.knowledge_manager import get_operation_logs as get_logs

        logs = get_logs(limit=limit)
        return {
            "success": True,
            "total": len(logs),
            "logs": logs,
        }
