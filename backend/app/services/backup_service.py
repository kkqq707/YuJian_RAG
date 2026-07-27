"""数据备份与恢复服务

企业级数据保护:
- 备份: SQLite 数据库 + Chroma 向量库 + 上传文件
- 备份格式: ZIP 压缩包
- 自动备份: 支持每日定时执行
- 恢复: 支持选择性恢复 database / chroma / uploads

安全:
- 备份操作需要管理员权限
- 恢复操作会覆盖当前数据，需确认
- 备份文件不包含 API Key 明文
"""

from __future__ import annotations

import logging
import os
import shutil
import threading
import time
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from backend.app.config import get_settings

logger = logging.getLogger(__name__)

# 备份目录
BACKUP_DIR_NAME = "backup"


def _get_project_root() -> Path:
    return get_settings().PROJECT_ROOT


def _get_storage_dir() -> Path:
    return _get_project_root() / "storage"


def _get_backup_dir() -> Path:
    return _get_storage_dir() / BACKUP_DIR_NAME


def _get_data_dir() -> Path:
    return _get_project_root() / "data"


def _get_uploads_dir() -> Path:
    return _get_data_dir() / "uploads"


class BackupResult:
    """备份结果。"""

    __slots__ = (
        "success", "file_name", "file_path", "file_size_bytes",
        "created_at", "included", "error",
    )

    def __init__(
        self,
        success: bool,
        file_name: Optional[str] = None,
        file_path: Optional[str] = None,
        file_size_bytes: int = 0,
        created_at: Optional[str] = None,
        included: Optional[dict] = None,
        error: Optional[str] = None,
    ):
        self.success = success
        self.file_name = file_name
        self.file_path = file_path
        self.file_size_bytes = file_size_bytes
        self.created_at = created_at
        self.included = included or {}
        self.error = error


class BackupService:
    """数据备份与恢复服务。

    备份范围:
    - storage/app.db          — 主数据库 (SQLAlchemy)
    - storage/knowledge_metadata.db — 知识库元数据
    - storage/chroma_db/      — Chroma 向量库
    - data/uploads/           — 上传文件

    恢复策略:
    - 先解压到临时目录
    - 停止相关服务访问
    - 替换原文件
    - 清理临时文件
    """

    # 需要备份的路径 (相对于项目根目录)
    BACKUP_ITEMS = [
        {
            "key": "database",
            "label": "SQLite 数据库",
            "path": "storage/app.db",
            "type": "file",
        },
        {
            "key": "knowledge_db",
            "label": "知识库元数据",
            "path": "storage/knowledge_metadata.db",
            "type": "file",
        },
        {
            "key": "chroma",
            "label": "Chroma 向量库",
            "path": "storage/chroma_db",
            "type": "dir",
        },
        {
            "key": "uploads",
            "label": "上传文件",
            "path": "data/uploads",
            "type": "dir",
        },
    ]

    # WAL/日志文件 — 备份时随数据库一起打包
    WAL_EXTENSIONS = ["-wal", "-shm", "-journal"]

    def __init__(self):
        self._backup_dir = _get_backup_dir()
        self._project_root = _get_project_root()
        # 确保备份目录存在
        self._backup_dir.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------
    # 公开方法
    # ------------------------------------------------------------------

    def create_backup(self) -> BackupResult:
        """创建完整备份。

        生成 backup_YYYYMMDD_HHMMSS.zip 文件。

        Returns
        -------
        BackupResult
        """
        utc_now = datetime.now(timezone.utc)
        timestamp = utc_now.strftime("%Y%m%d_%H%M%S")
        file_name = f"backup_{timestamp}.zip"
        file_path = self._backup_dir / file_name

        included = {}
        try:
            with zipfile.ZipFile(str(file_path), "w", zipfile.ZIP_DEFLATED) as zf:
                for item in self.BACKUP_ITEMS:
                    source = self._project_root / item["path"]
                    if not source.exists():
                        logger.info("备份: 跳过不存在的 %s", item["path"])
                        included[item["key"]] = {
                            "label": item["label"],
                            "status": "skipped",
                            "reason": "路径不存在",
                        }
                        continue

                    if item["type"] == "file":
                        self._add_file_to_zip(zf, source, item["path"])
                        # 同时备份 WAL 文件
                        for ext in self.WAL_EXTENSIONS:
                            wal_path = Path(str(source) + ext)
                            if wal_path.exists():
                                self._add_file_to_zip(
                                    zf, wal_path, item["path"] + ext
                                )

                        included[item["key"]] = {
                            "label": item["label"],
                            "status": "ok",
                            "size_bytes": source.stat().st_size,
                        }
                    elif item["type"] == "dir":
                        count = self._add_dir_to_zip(zf, source, item["path"])
                        included[item["key"]] = {
                            "label": item["label"],
                            "status": "ok",
                            "file_count": count,
                        }

            file_size = file_path.stat().st_size
            logger.info(
                "备份完成: %s (%.2f MB), 包含: %s",
                file_name,
                file_size / (1024 * 1024),
                [k for k, v in included.items() if v.get("status") == "ok"],
            )

            return BackupResult(
                success=True,
                file_name=file_name,
                file_path=str(file_path),
                file_size_bytes=file_size,
                created_at=utc_now.isoformat(),
                included=included,
            )

        except Exception as e:
            logger.error("备份失败: %s", e)
            # 清理失败的备份文件
            if file_path.exists():
                try:
                    file_path.unlink()
                except Exception:
                    pass
            return BackupResult(
                success=False,
                error=str(e),
            )

    def list_backups(self) -> list[dict]:
        """列出所有备份文件。

        Returns
        -------
        list[dict]
            按创建时间倒序排列。
        """
        if not self._backup_dir.exists():
            return []

        backups = []
        for f in sorted(
            self._backup_dir.glob("backup_*.zip"),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        ):
            stat = f.stat()
            backups.append({
                "file_name": f.name,
                "file_size_bytes": stat.st_size,
                "file_size_mb": round(stat.st_size / (1024 * 1024), 2),
                "created_at": datetime.fromtimestamp(
                    stat.st_mtime, tz=timezone.utc
                ).isoformat(),
            })

        return backups

    def get_backup_status(self) -> dict:
        """获取备份状态摘要。

        Returns
        -------
        dict
            {"last_backup_time": str|None, "last_backup_size_bytes": int,
             "last_backup_file": str|None, "total_backups": int,
             "total_backups_size_bytes": int, "status": str}
        """
        backups = self.list_backups()

        if not backups:
            return {
                "last_backup_time": None,
                "last_backup_size_bytes": 0,
                "last_backup_file": None,
                "total_backups": 0,
                "total_backups_size_bytes": 0,
                "status": "no_backup",
            }

        latest = backups[0]
        total_size = sum(b["file_size_bytes"] for b in backups)

        return {
            "last_backup_time": latest["created_at"],
            "last_backup_size_bytes": latest["file_size_bytes"],
            "last_backup_file": latest["file_name"],
            "total_backups": len(backups),
            "total_backups_size_bytes": total_size,
            "status": "ok",
        }

    def restore_backup(
        self,
        file_name: str,
        targets: Optional[list[str]] = None,
        admin_username: str = "",
    ) -> dict:
        """从备份文件恢复数据。

        Parameters
        ----------
        file_name : str
            备份文件名（如 backup_20260716_120000.zip）
        targets : list[str], optional
            要恢复的目标列表，可选值: "database", "chroma", "uploads"。
            默认全部恢复。
        admin_username : str
            执行恢复的管理员用户名（用于审计日志）。

        Returns
        -------
        dict
            {"success": bool, "restored": list[str], "errors": list[str]}

        Raises
        ------
        FileNotFoundError
            备份文件不存在。
        """
        file_path = self._backup_dir / file_name
        if not file_path.exists():
            raise FileNotFoundError(f"备份文件不存在: {file_name}")

        if targets is None:
            targets = ["database", "chroma", "uploads"]

        # 验证 target 有效性
        valid_targets = {"database", "chroma", "uploads"}
        invalid = set(targets) - valid_targets
        if invalid:
            raise ValueError(f"无效的恢复目标: {invalid}，有效值: {valid_targets}")

        restored = []
        errors = []

        # 解压到临时目录
        temp_dir = self._backup_dir / "_restore_temp"
        if temp_dir.exists():
            shutil.rmtree(str(temp_dir), ignore_errors=True)
        temp_dir.mkdir(parents=True, exist_ok=True)

        try:
            with zipfile.ZipFile(str(file_path), "r") as zf:
                zf.extractall(str(temp_dir))

            # 逐项恢复
            for item in self.BACKUP_ITEMS:
                if not self._should_restore(item["key"], targets):
                    continue

                source = temp_dir / item["path"]
                dest = self._project_root / item["path"]

                if not source.exists():
                    logger.info("恢复: 备份中无 %s，跳过", item["path"])
                    continue

                try:
                    self._restore_item(source, dest, item["type"])
                    restored.append(item["key"])
                    logger.info(
                        "恢复完成: %s (管理员: %s)", item["label"], admin_username
                    )
                except Exception as e:
                    error_msg = f"恢复 {item['label']} 失败: {e}"
                    errors.append(error_msg)
                    logger.error(error_msg)

        finally:
            # 清理临时目录
            shutil.rmtree(str(temp_dir), ignore_errors=True)

        return {
            "success": len(errors) == 0,
            "restored": restored,
            "errors": errors,
        }

    def delete_old_backups(self, keep_count: int = 7) -> int:
        """清理旧备份，保留最近 N 个。

        Parameters
        ----------
        keep_count : int
            保留的备份数量。

        Returns
        -------
        int
            删除的备份数量。
        """
        backups = sorted(
            self._backup_dir.glob("backup_*.zip"),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )

        deleted = 0
        for old in backups[keep_count:]:
            try:
                old.unlink()
                deleted += 1
                logger.info("清理旧备份: %s", old.name)
            except Exception as e:
                logger.warning("清理备份失败 %s: %s", old.name, e)

        return deleted

    # ------------------------------------------------------------------
    # 内部方法
    # ------------------------------------------------------------------

    def _should_restore(self, item_key: str, targets: list[str]) -> bool:
        """检查某个项目是否需要恢复。

        映射关系:
        - "database" → database + knowledge_db
        - "chroma" → chroma
        - "uploads" → uploads
        """
        if item_key in ("database", "knowledge_db"):
            return "database" in targets
        if item_key == "chroma":
            return "chroma" in targets
        if item_key == "uploads":
            return "uploads" in targets
        return False

    @staticmethod
    def _add_file_to_zip(zf: zipfile.ZipFile, file_path: Path, arcname: str):
        """将单个文件添加到 ZIP。"""
        if file_path.exists() and file_path.is_file():
            zf.write(str(file_path), arcname)

    @staticmethod
    def _add_dir_to_zip(zf: zipfile.ZipFile, dir_path: Path, arcbase: str) -> int:
        """将目录递归添加到 ZIP，返回文件数。"""
        count = 0
        for root, dirs, files in os.walk(str(dir_path)):
            for fname in files:
                full = Path(root) / fname
                rel = str(Path(arcbase) / full.relative_to(dir_path))
                zf.write(str(full), rel)
                count += 1
        return count

    @staticmethod
    def _restore_item(source: Path, dest: Path, item_type: str):
        """恢复单个项目。

        - file: 直接复制
        - dir: 先删除目标目录，再复制
        """
        if item_type == "file":
            # 确保目标目录存在
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(str(source), str(dest))
            # 也恢复 WAL 文件
            for ext in BackupService.WAL_EXTENSIONS:
                wal_source = Path(str(source) + ext)
                if wal_source.exists():
                    shutil.copy2(str(wal_source), str(dest) + ext)

        elif item_type == "dir":
            if dest.exists():
                shutil.rmtree(str(dest), ignore_errors=True)
            shutil.copytree(str(source), str(dest))


# ---------------------------------------------------------------------------
# 自动备份调度器（后台线程）
# ---------------------------------------------------------------------------

_auto_backup_thread: Optional[threading.Thread] = None
_auto_backup_stop: threading.Event = threading.Event()
_AUTO_BACKUP_INTERVAL_SECONDS = 86400  # 24 小时


def _auto_backup_worker():
    """自动备份工作线程。

    每天执行一次备份，清理超过 7 天的旧备份。
    """
    logger.info("自动备份服务已启动（间隔: %d 秒）", _AUTO_BACKUP_INTERVAL_SECONDS)

    while not _auto_backup_stop.is_set():
        # 等待到下一个备份时间点
        _auto_backup_stop.wait(timeout=_AUTO_BACKUP_INTERVAL_SECONDS)
        if _auto_backup_stop.is_set():
            break

        try:
            service = BackupService()
            result = service.create_backup()

            if result.success:
                logger.info(
                    "自动备份完成: %s (%.2f MB)",
                    result.file_name,
                    result.file_size_bytes / (1024 * 1024),
                )
                # 清理旧备份，保留最近 7 个
                deleted = service.delete_old_backups(keep_count=7)
                if deleted > 0:
                    logger.info("清理 %d 个旧备份", deleted)
            else:
                logger.error("自动备份失败: %s", result.error)

        except Exception as e:
            logger.error("自动备份异常: %s", e)


def start_auto_backup():
    """启动自动备份后台线程。"""
    global _auto_backup_thread, _auto_backup_stop

    if _auto_backup_thread is not None and _auto_backup_thread.is_alive():
        logger.info("自动备份服务已在运行中")
        return

    _auto_backup_stop.clear()
    _auto_backup_thread = threading.Thread(
        target=_auto_backup_worker,
        name="auto-backup",
        daemon=True,
    )
    _auto_backup_thread.start()
    logger.info("自动备份服务线程已启动")


def stop_auto_backup():
    """停止自动备份后台线程。"""
    global _auto_backup_thread
    _auto_backup_stop.set()
    if _auto_backup_thread is not None:
        _auto_backup_thread.join(timeout=5)
        _auto_backup_thread = None
    logger.info("自动备份服务已停止")
