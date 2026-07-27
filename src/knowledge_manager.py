"""知识库元数据管理模块

使用 SQLite (storage/knowledge_metadata.db) 管理上传文件元数据。
提供查询、添加、更新状态、逻辑删除等功能。

安全策略:
- 不存储文件正文
- 不存储 API Key
- 不存储完整聊天上下文
- error_message 安全化
"""

from __future__ import annotations

import logging
import sqlite3
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock
from typing import Optional

from src import config

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# 常量
# ---------------------------------------------------------------------------

# 数据库版本，用于未来迁移
_DB_VERSION = 3

# 上传状态
UPLOAD_STATUS_UPLOADED = "uploaded"
UPLOAD_STATUS_PARSING = "parsing"
UPLOAD_STATUS_FAILED = "failed"

# 索引状态
INDEX_STATUS_PENDING = "pending"
INDEX_STATUS_PROCESSING = "processing"
INDEX_STATUS_INDEXED = "indexed"
INDEX_STATUS_FAILED = "failed"
INDEX_STATUS_DELETED = "deleted"

# Embedding 状态（新增）
EMBEDDING_STATUS_PENDING = "pending"
EMBEDDING_STATUS_EMBEDDING = "embedding"
EMBEDDING_STATUS_COMPLETED = "completed"
EMBEDDING_STATUS_FAILED = "failed"

# 索引任务状态（新增）
INDEX_TASK_PREPARING = "preparing"
INDEX_TASK_CLEANING = "cleaning"
INDEX_TASK_REPARSING = "reparsing"
INDEX_TASK_EMBEDDING = "embedding"
INDEX_TASK_WRITING = "writing"
INDEX_TASK_COMPLETED = "completed"
INDEX_TASK_FAILED = "failed"

# 文件来源类型
SOURCE_TYPE_BUILTIN = "builtin"
SOURCE_TYPE_UPLOAD = "upload"

# 版本变更类型
CHANGE_TYPE_CREATE = "create"
CHANGE_TYPE_UPDATE = "update"
CHANGE_TYPE_ROLLBACK = "rollback"

# ---------------------------------------------------------------------------
# 数据库初始化
# ---------------------------------------------------------------------------

_connection_lock = Lock()


def _get_connection() -> sqlite3.Connection:
    """获取 SQLite 连接（线程安全）。"""
    conn = sqlite3.connect(str(config.METADATA_DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_database() -> None:
    """初始化知识库元数据数据库（幂等操作）。

    自动检测并执行数据库迁移，从旧版本逐步升级到最新版本。
    """
    config.METADATA_DB_PATH.parent.mkdir(parents=True, exist_ok=True)

    with _connection_lock:
        conn = _get_connection()
        try:
            # ---- 基础表创建 ----
            conn.execute("""
                CREATE TABLE IF NOT EXISTS knowledge_files (
                    id TEXT PRIMARY KEY,
                    original_name TEXT NOT NULL,
                    stored_name TEXT NOT NULL,
                    stored_path TEXT NOT NULL,
                    file_type TEXT NOT NULL,
                    file_size INTEGER NOT NULL,
                    file_hash TEXT NOT NULL,
                    source_type TEXT NOT NULL DEFAULT 'upload',
                    upload_status TEXT NOT NULL DEFAULT 'uploaded',
                    index_status TEXT NOT NULL DEFAULT 'pending',
                    upload_time TEXT NOT NULL,
                    indexed_time TEXT,
                    error_message TEXT,
                    chunk_count INTEGER DEFAULT 0,
                    is_active INTEGER DEFAULT 1,
                    metadata_json TEXT DEFAULT '{}',
                    tenant_id TEXT NOT NULL DEFAULT 'default',
                    update_time TEXT,
                    embedding_status TEXT NOT NULL DEFAULT 'pending',
                    current_version TEXT NOT NULL DEFAULT 'v1',
                    last_index_time TEXT,
                    preview_available INTEGER DEFAULT 0
                )
            """)

            conn.execute("""
                CREATE TABLE IF NOT EXISTS builtin_files (
                    id TEXT PRIMARY KEY,
                    original_name TEXT NOT NULL,
                    stored_path TEXT NOT NULL,
                    file_type TEXT NOT NULL,
                    file_size INTEGER NOT NULL,
                    file_hash TEXT NOT NULL,
                    source_type TEXT NOT NULL DEFAULT 'builtin',
                    index_status TEXT NOT NULL DEFAULT 'indexed',
                    indexed_time TEXT,
                    chunk_count INTEGER DEFAULT 0,
                    is_active INTEGER DEFAULT 1
                )
            """)

            # ---- index_task 表 ----
            conn.execute("""
                CREATE TABLE IF NOT EXISTS index_tasks (
                    id TEXT PRIMARY KEY,
                    status TEXT NOT NULL DEFAULT 'preparing',
                    progress INTEGER DEFAULT 0,
                    total_files INTEGER DEFAULT 0,
                    success_count INTEGER DEFAULT 0,
                    failed_count INTEGER DEFAULT 0,
                    total_chunks INTEGER DEFAULT 0,
                    start_time TEXT NOT NULL,
                    end_time TEXT,
                    error_message TEXT,
                    triggered_by TEXT NOT NULL DEFAULT 'admin'
                )
            """)

            # ---- 版本历史表（新增）----
            conn.execute("""
                CREATE TABLE IF NOT EXISTS knowledge_file_versions (
                    id TEXT PRIMARY KEY,
                    file_id TEXT NOT NULL,
                    version TEXT NOT NULL,
                    file_hash TEXT NOT NULL,
                    file_size INTEGER NOT NULL,
                    operator TEXT NOT NULL DEFAULT 'admin',
                    created_time TEXT NOT NULL,
                    change_type TEXT NOT NULL DEFAULT 'create',
                    stored_name TEXT NOT NULL DEFAULT '',
                    FOREIGN KEY (file_id) REFERENCES knowledge_files(id)
                )
            """)

            # ---- 操作日志表（新增）----
            conn.execute("""
                CREATE TABLE IF NOT EXISTS operation_logs (
                    id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL DEFAULT 'admin',
                    operation TEXT NOT NULL,
                    target TEXT NOT NULL,
                    time TEXT NOT NULL,
                    result TEXT NOT NULL DEFAULT 'success'
                )
            """)

            # 版本信息
            conn.execute("""
                CREATE TABLE IF NOT EXISTS schema_version (
                    version INTEGER PRIMARY KEY,
                    updated_at TEXT NOT NULL
                )
            """)

            # ---- 自动迁移 ----
            _run_migrations(conn)

            # 更新版本记录
            conn.execute(
                "INSERT OR REPLACE INTO schema_version (version, updated_at) VALUES (?, ?)",
                (_DB_VERSION, datetime.now(timezone.utc).isoformat()),
            )

            conn.commit()
        finally:
            conn.close()


def _run_migrations(conn: sqlite3.Connection) -> None:
    """执行数据库迁移（幂等）。"""
    current_version = conn.execute(
        "SELECT MAX(version) FROM schema_version"
    ).fetchone()[0] or 0

    # V1 → V2: 添加 update_time, embedding_status 列
    if current_version < 2:
        for col, default_val in [
            ("update_time", "TEXT"),
            ("embedding_status", "TEXT NOT NULL DEFAULT 'completed'"),
        ]:
            try:
                conn.execute(
                    f"ALTER TABLE knowledge_files ADD COLUMN {col} {default_val}"
                )
            except Exception:
                pass  # 列已存在则忽略

        # 已有记录的 embedding_status 设为 completed（向后兼容）
        conn.execute(
            "UPDATE knowledge_files SET embedding_status = 'completed' "
            "WHERE index_status = 'indexed' AND (embedding_status IS NULL OR embedding_status = 'pending')"
        )

    # V2 → V3: 添加 current_version, last_index_time, preview_available 列
    if current_version < 3:
        for col, default_val in [
            ("current_version", "TEXT NOT NULL DEFAULT 'v1'"),
            ("last_index_time", "TEXT"),
            ("preview_available", "INTEGER DEFAULT 0"),
        ]:
            try:
                conn.execute(
                    f"ALTER TABLE knowledge_files ADD COLUMN {col} {default_val}"
                )
            except Exception:
                pass  # 列已存在则忽略

        # 为已有活跃文件创建初始版本记录 (v1)
        existing_files = conn.execute(
            "SELECT id, file_hash, file_size, upload_time FROM knowledge_files "
            "WHERE is_active = 1"
        ).fetchall()
        for row in existing_files:
            version_id = str(uuid.uuid4())
            try:
                conn.execute(
                    """INSERT OR IGNORE INTO knowledge_file_versions
                       (id, file_id, version, file_hash, file_size, operator,
                        created_time, change_type, stored_name)
                       VALUES (?, ?, 'v1', ?, ?, 'admin', ?, 'create', '')""",
                    (version_id, row["id"], row["file_hash"], row["file_size"],
                     row["upload_time"]),
                )
            except Exception:
                pass


# ---------------------------------------------------------------------------
# 公开函数 — 查询
# ---------------------------------------------------------------------------


def get_file_by_id(file_id: str) -> dict | None:
    """根据 ID 查询文件记录。

    Parameters
    ----------
    file_id : str

    Returns
    -------
    dict | None
    """
    conn = _get_connection()
    try:
        row = conn.execute(
            "SELECT * FROM knowledge_files WHERE id = ?",
            (file_id,)
        ).fetchone()
        if row:
            return dict(row)
        return None
    finally:
        conn.close()


def get_file_by_hash(file_hash: str) -> dict | None:
    """根据 SHA-256 哈希查询文件记录（用于重复检测）。

    Parameters
    ----------
    file_hash : str

    Returns
    -------
    dict | None
    """
    conn = _get_connection()
    try:
        row = conn.execute(
            "SELECT * FROM knowledge_files WHERE file_hash = ? AND is_active = 1",
            (file_hash,)
        ).fetchone()
        if row:
            return dict(row)
        return None
    finally:
        conn.close()


def get_all_active_files(source_type: str | None = None) -> list[dict]:
    """获取所有活跃文件列表。

    Parameters
    ----------
    source_type : str, optional
        过滤来源类型: 'builtin' | 'upload'。为 None 时返回所有。

    Returns
    -------
    list[dict]
    """
    conn = _get_connection()
    try:
        if source_type:
            rows = conn.execute(
                "SELECT * FROM knowledge_files WHERE is_active = 1 AND source_type = ? "
                "ORDER BY upload_time DESC",
                (source_type,)
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM knowledge_files WHERE is_active = 1 "
                "ORDER BY upload_time DESC"
            ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def get_pending_files() -> list[dict]:
    """获取所有待索引的文件。

    Returns
    -------
    list[dict]
    """
    conn = _get_connection()
    try:
        rows = conn.execute(
            "SELECT * FROM knowledge_files "
            "WHERE is_active = 1 AND source_type = 'upload' "
            "AND index_status IN ('pending', 'failed') "
            "ORDER BY upload_time ASC"
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def get_files_by_upload_ids(upload_ids: list[str]) -> list[dict]:
    """根据 upload_id 列表批量查询。

    Parameters
    ----------
    upload_ids : list[str]

    Returns
    -------
    list[dict]
    """
    if not upload_ids:
        return []
    conn = _get_connection()
    try:
        placeholders = ",".join("?" for _ in upload_ids)
        rows = conn.execute(
            f"SELECT * FROM knowledge_files WHERE id IN ({placeholders})",
            upload_ids,
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def get_statistics() -> dict:
    """获取知识库统计信息。

    Returns
    -------
    dict
    """
    conn = _get_connection()
    try:
        total_uploads = conn.execute(
            "SELECT COUNT(*) as cnt FROM knowledge_files "
            "WHERE source_type = 'upload' AND is_active = 1"
        ).fetchone()["cnt"]

        indexed_uploads = conn.execute(
            "SELECT COUNT(*) as cnt FROM knowledge_files "
            "WHERE source_type = 'upload' AND is_active = 1 AND index_status = 'indexed'"
        ).fetchone()["cnt"]

        total_chunks = conn.execute(
            "SELECT COALESCE(SUM(chunk_count), 0) as cnt FROM knowledge_files "
            "WHERE is_active = 1 AND index_status = 'indexed'"
        ).fetchone()["cnt"]

        last_update = conn.execute(
            "SELECT MAX(indexed_time) as t FROM knowledge_files "
            "WHERE is_active = 1 AND index_status = 'indexed'"
        ).fetchone()["t"]

        return {
            "total_uploaded_files": total_uploads,
            "indexed_files": indexed_uploads,
            "total_chunks": total_chunks,
            "last_update_time": last_update or "N/A",
        }
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# 公开函数 — 写入
# ---------------------------------------------------------------------------


def add_file_record(
    original_name: str,
    stored_name: str,
    stored_path: str,
    file_type: str,
    file_size: int,
    file_hash: str,
    source_type: str = SOURCE_TYPE_UPLOAD,
    tenant_id: str = "default",
) -> str:
    """添加文件元数据记录。

    Parameters
    ----------
    original_name : str
        原始文件名
    stored_name : str
        存储文件名 ({upload_id}_{safe_name})
    stored_path : str
        文件存储路径（相对路径或仅文件名）
    file_type : str
        文件扩展名
    file_size : int
        文件大小（字节）
    file_hash : str
        SHA-256 哈希
    source_type : str
        来源类型
    tenant_id : str
        租户 ID，默认为 "default"

    Returns
    -------
    str
        生成的 upload_id

    Raises
    ------
    ValueError
        相同哈希的文件已存在
    """
    # 重复检测
    existing = get_file_by_hash(file_hash)
    if existing and existing.get("is_active"):
        raise ValueError(
            f"文件已存在（原文件名: {existing.get('original_name', '未知')}），"
            f"相同内容的文件无需重复上传"
        )

    file_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()

    conn = _get_connection()
    try:
        conn.execute(
            """INSERT INTO knowledge_files
               (id, original_name, stored_name, stored_path, file_type, file_size,
                file_hash, source_type, upload_status, index_status, upload_time, tenant_id)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                file_id,
                original_name,
                stored_name,
                stored_path,
                file_type,
                file_size,
                file_hash,
                source_type,
                UPLOAD_STATUS_UPLOADED,
                INDEX_STATUS_PENDING,
                now,
                tenant_id,
            ),
        )
        conn.commit()
        logger.info("文件记录已添加: %s (id=%s)", original_name, file_id)
        return file_id
    finally:
        conn.close()


def add_builtin_record(
    original_name: str,
    stored_path: str,
    file_type: str,
    file_size: int,
    file_hash: str,
) -> str:
    """为内置知识库文件添加元数据记录（幂等：同路径文件不重复添加）。

    Parameters
    ----------
    original_name : str
    stored_path : str
    file_type : str
    file_size : int
    file_hash : str

    Returns
    -------
    str
        file_id
    """
    conn = _get_connection()
    try:
        # 检查是否已存在
        existing = conn.execute(
            "SELECT id FROM builtin_files WHERE stored_path = ? AND is_active = 1",
            (stored_path,)
        ).fetchone()
        if existing:
            return existing["id"]

        file_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc).isoformat()

        conn.execute(
            """INSERT INTO builtin_files
               (id, original_name, stored_path, file_type, file_size,
                file_hash, source_type, index_status, indexed_time)
               VALUES (?, ?, ?, ?, ?, ?, ?, 'indexed', ?)""",
            (file_id, original_name, stored_path, file_type, file_size, file_hash, now),
        )
        conn.commit()
        return file_id
    finally:
        conn.close()


def update_index_status(
    file_id: str,
    index_status: str,
    chunk_count: int = 0,
    error_message: str | None = None,
    embedding_status: str | None = None,
) -> None:
    """更新文件索引状态。

    Parameters
    ----------
    file_id : str
    index_status : str
    chunk_count : int
    error_message : str, optional
    embedding_status : str, optional
        如果提供，同步更新 embedding_status
    """
    now = datetime.now(timezone.utc).isoformat() if index_status == INDEX_STATUS_INDEXED else None
    update_now = datetime.now(timezone.utc).isoformat()

    # error_message 安全化
    safe_error = None
    if error_message:
        safe_error = str(error_message).split("\n")[0][:300]

    conn = _get_connection()
    try:
        if now:
            conn.execute(
                """UPDATE knowledge_files
                   SET index_status = ?, chunk_count = ?, error_message = ?, indexed_time = ?,
                       update_time = ?, embedding_status = COALESCE(?, embedding_status)
                   WHERE id = ?""",
                (index_status, chunk_count, safe_error, now,
                 update_now, embedding_status, file_id),
            )
        else:
            conn.execute(
                """UPDATE knowledge_files
                   SET index_status = ?, chunk_count = ?, error_message = ?,
                       update_time = ?, embedding_status = COALESCE(?, embedding_status)
                   WHERE id = ?""",
                (index_status, chunk_count, safe_error,
                 update_now, embedding_status, file_id),
            )
        conn.commit()
    finally:
        conn.close()


def reset_all_index_status(source_type: str = SOURCE_TYPE_UPLOAD) -> int:
    """将所有活跃文件的索引状态重置为 'pending'。

    在重建索引前调用，清除旧的 chunk_count、error_message 和 indexed_time。
    仅影响 source_type 匹配且 is_active=1 的记录。

    Parameters
    ----------
    source_type : str
        要重置的文件来源类型，默认 'upload'

    Returns
    -------
    int
        更新的记录数
    """
    conn = _get_connection()
    try:
        cursor = conn.execute(
            """UPDATE knowledge_files
               SET index_status = ?, chunk_count = 0, error_message = NULL,
                   indexed_time = NULL
               WHERE source_type = ? AND is_active = 1""",
            (INDEX_STATUS_PENDING, source_type),
        )
        conn.commit()
        count = cursor.rowcount
        logger.info("已重置 %d 条 %s 文件记录的状态为 pending", count, source_type)
        return count
    finally:
        conn.close()


def soft_delete_file(file_id: str) -> None:
    """逻辑删除文件（将 is_active 设为 0，index_status 设为 deleted）。

    Parameters
    ----------
    file_id : str
    """
    conn = _get_connection()
    try:
        conn.execute(
            """UPDATE knowledge_files
               SET is_active = 0, index_status = ?, error_message = NULL
               WHERE id = ?""",
            (INDEX_STATUS_DELETED, file_id),
        )
        conn.commit()
        logger.info("文件已逻辑删除: %s", file_id)
    finally:
        conn.close()


def get_upload_count() -> int:
    """获取已上传文件数量。

    Returns
    -------
    int
    """
    conn = _get_connection()
    try:
        row = conn.execute(
            "SELECT COUNT(*) as cnt FROM knowledge_files "
            "WHERE source_type = 'upload' AND is_active = 1"
        ).fetchone()
        return row["cnt"] if row else 0
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# 公开函数 — index_task 管理
# ---------------------------------------------------------------------------


def create_index_task(
    total_files: int = 0,
    triggered_by: str = "admin",
) -> str:
    """创建索引任务记录，返回任务 ID。

    Parameters
    ----------
    total_files : int
        待索引文件总数
    triggered_by : str
        触发来源: 'admin' | 'system'

    Returns
    -------
    str
        task_id
    """
    task_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()

    conn = _get_connection()
    try:
        conn.execute(
            """INSERT INTO index_tasks
               (id, status, total_files, start_time, triggered_by)
               VALUES (?, ?, ?, ?, ?)""",
            (task_id, INDEX_TASK_PREPARING, total_files, now, triggered_by),
        )
        conn.commit()
        logger.info("索引任务已创建: %s (total_files=%d)", task_id, total_files)
        return task_id
    finally:
        conn.close()


def update_index_task(
    task_id: str,
    status: str | None = None,
    progress: int | None = None,
    success_count: int | None = None,
    failed_count: int | None = None,
    total_chunks: int | None = None,
    error_message: str | None = None,
) -> None:
    """更新索引任务状态。

    Parameters
    ----------
    task_id : str
    status : str, optional
    progress : int, optional
    success_count : int, optional
    failed_count : int, optional
    total_chunks : int, optional
    error_message : str, optional
    """
    fields = []
    values = []

    if status is not None:
        fields.append("status = ?")
        values.append(status)
    if progress is not None:
        fields.append("progress = ?")
        values.append(progress)
    if success_count is not None:
        fields.append("success_count = ?")
        values.append(success_count)
    if failed_count is not None:
        fields.append("failed_count = ?")
        values.append(failed_count)
    if total_chunks is not None:
        fields.append("total_chunks = ?")
        values.append(total_chunks)
    if error_message is not None:
        safe_error = str(error_message).split("\n")[0][:300]
        fields.append("error_message = ?")
        values.append(safe_error)

    if status in (INDEX_TASK_COMPLETED, INDEX_TASK_FAILED):
        fields.append("end_time = ?")
        values.append(datetime.now(timezone.utc).isoformat())

    if not fields:
        return

    values.append(task_id)

    conn = _get_connection()
    try:
        conn.execute(
            f"UPDATE index_tasks SET {', '.join(fields)} WHERE id = ?",
            values,
        )
        conn.commit()
    finally:
        conn.close()


def get_index_task(task_id: str) -> dict | None:
    """获取索引任务详情。

    Parameters
    ----------
    task_id : str

    Returns
    -------
    dict | None
    """
    conn = _get_connection()
    try:
        row = conn.execute(
            "SELECT * FROM index_tasks WHERE id = ?",
            (task_id,),
        ).fetchone()
        if row:
            return dict(row)
        return None
    finally:
        conn.close()


def get_latest_index_task() -> dict | None:
    """获取最近的索引任务。

    Returns
    -------
    dict | None
    """
    conn = _get_connection()
    try:
        row = conn.execute(
            "SELECT * FROM index_tasks ORDER BY start_time DESC LIMIT 1"
        ).fetchone()
        if row:
            return dict(row)
        return None
    finally:
        conn.close()


def get_all_index_tasks(limit: int = 20) -> list[dict]:
    """获取所有索引任务列表。

    Parameters
    ----------
    limit : int
        返回条数限制

    Returns
    -------
    list[dict]
    """
    conn = _get_connection()
    try:
        rows = conn.execute(
            "SELECT * FROM index_tasks ORDER BY start_time DESC LIMIT ?",
            (limit,),
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# 公开函数 — 版本管理
# ---------------------------------------------------------------------------


def create_file_version(
    file_id: str,
    version: str,
    file_hash: str,
    file_size: int,
    operator: str = "admin",
    change_type: str = CHANGE_TYPE_CREATE,
    stored_name: str = "",
) -> str:
    """创建文件版本记录。

    Parameters
    ----------
    file_id : str
        文件记录 ID
    version : str
        版本号，如 v1, v2
    file_hash : str
        SHA-256 哈希
    file_size : int
        文件大小（字节）
    operator : str
        操作者
    change_type : str
        变更类型: create | update | rollback
    stored_name : str
        该版本对应的存储文件名

    Returns
    -------
    str
        version_id
    """
    version_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()

    conn = _get_connection()
    try:
        conn.execute(
            """INSERT INTO knowledge_file_versions
               (id, file_id, version, file_hash, file_size, operator,
                created_time, change_type, stored_name)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (version_id, file_id, version, file_hash, file_size,
             operator, now, change_type, stored_name),
        )
        conn.commit()
        logger.info(
            "版本记录已创建: file_id=%s, version=%s, change_type=%s",
            file_id, version, change_type,
        )
        return version_id
    finally:
        conn.close()


def get_file_versions(file_id: str) -> list[dict]:
    """获取文件的所有版本记录。

    Parameters
    ----------
    file_id : str

    Returns
    -------
    list[dict]
    """
    conn = _get_connection()
    try:
        rows = conn.execute(
            "SELECT * FROM knowledge_file_versions "
            "WHERE file_id = ? ORDER BY created_time DESC",
            (file_id,),
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def get_version_by_id(version_id: str) -> dict | None:
    """根据版本 ID 查询版本记录。

    Parameters
    ----------
    version_id : str

    Returns
    -------
    dict | None
    """
    conn = _get_connection()
    try:
        row = conn.execute(
            "SELECT * FROM knowledge_file_versions WHERE id = ?",
            (version_id,),
        ).fetchone()
        if row:
            return dict(row)
        return None
    finally:
        conn.close()


def delete_version_record(version_id: str) -> bool:
    """删除版本记录。

    Parameters
    ----------
    version_id : str

    Returns
    -------
    bool
    """
    conn = _get_connection()
    try:
        conn.execute(
            "DELETE FROM knowledge_file_versions WHERE id = ?",
            (version_id,),
        )
        conn.commit()
        return True
    finally:
        conn.close()


def get_latest_version_number(file_id: str) -> int:
    """获取文件当前最新版本号（数字）。

    Parameters
    ----------
    file_id : str

    Returns
    -------
    int
    """
    conn = _get_connection()
    try:
        row = conn.execute(
            "SELECT version FROM knowledge_file_versions "
            "WHERE file_id = ? ORDER BY created_time DESC LIMIT 1",
            (file_id,),
        ).fetchone()
        if row:
            v = row["version"]
            try:
                return int(v.lstrip("v"))
            except ValueError:
                return 1
        return 1
    finally:
        conn.close()


def update_file_version_info(
    file_id: str,
    current_version: str,
    file_hash: str | None = None,
    file_size: int | None = None,
) -> None:
    """更新文件的版本信息。

    Parameters
    ----------
    file_id : str
    current_version : str
    file_hash : str, optional
    file_size : int, optional
    """
    now = datetime.now(timezone.utc).isoformat()
    conn = _get_connection()
    try:
        if file_hash is not None and file_size is not None:
            conn.execute(
                """UPDATE knowledge_files
                   SET current_version = ?, file_hash = ?, file_size = ?,
                       update_time = ?
                   WHERE id = ?""",
                (current_version, file_hash, file_size, now, file_id),
            )
        else:
            conn.execute(
                """UPDATE knowledge_files
                   SET current_version = ?, update_time = ?
                   WHERE id = ?""",
                (current_version, now, file_id),
            )
        conn.commit()
    finally:
        conn.close()


def update_file_preview_status(file_id: str, preview_available: bool = True) -> None:
    """更新文件预览状态。

    Parameters
    ----------
    file_id : str
    preview_available : bool
    """
    conn = _get_connection()
    try:
        conn.execute(
            "UPDATE knowledge_files SET preview_available = ? WHERE id = ?",
            (1 if preview_available else 0, file_id),
        )
        conn.commit()
    finally:
        conn.close()


def get_files_by_original_name(original_name: str) -> list[dict]:
    """按原始文件名查询所有活跃文件（用于版本检测）。

    Parameters
    ----------
    original_name : str

    Returns
    -------
    list[dict]
    """
    conn = _get_connection()
    try:
        rows = conn.execute(
            "SELECT * FROM knowledge_files "
            "WHERE original_name = ? AND is_active = 1 "
            "ORDER BY upload_time DESC",
            (original_name,),
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# 公开函数 — 操作日志
# ---------------------------------------------------------------------------


def add_operation_log(
    user_id: str,
    operation: str,
    target: str,
    result: str = "success",
) -> str:
    """记录操作日志。

    Parameters
    ----------
    user_id : str
    operation : str
        操作类型: upload_file | update_version | delete_file | reindex
    target : str
        操作目标描述
    result : str
        操作结果: success | failed

    Returns
    -------
    str
        log_id
    """
    log_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()
    conn = _get_connection()
    try:
        conn.execute(
            """INSERT INTO operation_logs (id, user_id, operation, target, time, result)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (log_id, user_id, operation, target, now, result),
        )
        conn.commit()
        return log_id
    finally:
        conn.close()


def get_operation_logs(limit: int = 50) -> list[dict]:
    """获取最近的操作日志。

    Parameters
    ----------
    limit : int

    Returns
    -------
    list[dict]
    """
    conn = _get_connection()
    try:
        rows = conn.execute(
            "SELECT * FROM operation_logs ORDER BY time DESC LIMIT ?",
            (limit,),
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()
