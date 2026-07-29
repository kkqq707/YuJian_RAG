"""磁盘空间监控服务 (Phase 10)

轻量级磁盘空间检查，用于:
- 管理系统状态接口显示磁盘使用
- 备份前检查空间
- 上传前检查空间
- 文档任务执行前检查空间

原则:
- 磁盘统计失败不导致主服务崩溃
- 超过阈值记录 WARNING
- 超过严重阈值禁止大文件上传/备份
"""

from __future__ import annotations

import logging
import os
import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from backend.app.config import get_settings

logger = logging.getLogger(__name__)

# 默认阈值
DISK_WARNING_PERCENT = 80
DISK_CRITICAL_PERCENT = 90
MIN_FREE_DISK_BYTES = 10 * 1024 * 1024 * 1024  # 10 GB


@dataclass
class DiskInfo:
    """单个磁盘/路径的空间信息。"""
    path: str
    total_bytes: int
    used_bytes: int
    free_bytes: int
    percent_used: float
    mount_point: str = ""


@dataclass
class DiskCheckResult:
    """磁盘检查结果。"""
    ok: bool
    warning: bool = False
    critical: bool = False
    message: str = ""
    disks: list[DiskInfo] = field(default_factory=list)


def _get_disk_usage(path: str) -> Optional[DiskInfo]:
    """获取单个路径的磁盘使用情况。

    使用 shutil.disk_usage，跨平台兼容。
    失败时返回 None，不抛异常。
    """
    try:
        usage = shutil.disk_usage(path)
        total = usage.total
        used = usage.used
        free = usage.free
        percent = (used / total) * 100 if total > 0 else 0

        return DiskInfo(
            path=path,
            total_bytes=total,
            used_bytes=used,
            free_bytes=free,
            percent_used=round(percent, 2),
        )
    except Exception as e:
        logger.warning("磁盘检查失败 [%s]: %s", path, str(e)[:150])
        return None


def _get_mount_point(path: str) -> str:
    """获取路径所在的挂载点。"""
    try:
        # 向上查找直到找到挂载点
        p = Path(path).resolve()
        while not p.is_mount() and p.parent != p:
            p = p.parent
        return str(p)
    except Exception:
        return path


def check_disk_space(
    warning_percent: int = DISK_WARNING_PERCENT,
    critical_percent: int = DISK_CRITICAL_PERCENT,
    min_free_bytes: int = MIN_FREE_DISK_BYTES,
) -> DiskCheckResult:
    """检查所有关键路径的磁盘空间。

    检查路径:
    - / (根分区)
    - storage/ (SQLite + Chroma + 日志)
    - data/ (上传文件)
    - backups/ (备份目录)

    Parameters
    ----------
    warning_percent : int
        警告阈值百分比 (默认 80%)
    critical_percent : int
        严重阈值百分比 (默认 90%)
    min_free_bytes : int
        最小可用空间字节数 (默认 10 GB)

    Returns
    -------
    DiskCheckResult
    """
    settings = get_settings()
    project_root = settings.PROJECT_ROOT

    paths_to_check = [
        str(project_root),
        str(settings.STORAGE_DIR),
        str(settings.DATA_DIR),
        str(project_root / "backups"),
    ]

    # 去重（多个路径可能在同一分区）
    seen_mounts: set[str] = set()
    disk_infos: list[DiskInfo] = []
    warning = False
    critical = False
    messages: list[str] = []

    for path in paths_to_check:
        info = _get_disk_usage(path)
        if info is None:
            continue

        # 按挂载点去重
        info.mount_point = _get_mount_point(path)
        if info.mount_point in seen_mounts:
            continue
        seen_mounts.add(info.mount_point)

        disk_infos.append(info)

        # 检查阈值
        if info.percent_used >= critical_percent:
            critical = True
            messages.append(
                f"[CRITICAL] {info.mount_point}: {info.percent_used:.1f}% 已用 "
                f"({_format_bytes(info.free_bytes)} 可用)"
            )
        elif info.percent_used >= warning_percent:
            warning = True
            messages.append(
                f"[WARNING] {info.mount_point}: {info.percent_used:.1f}% 已用 "
                f"({_format_bytes(info.free_bytes)} 可用)"
            )

        # 检查最小可用空间
        if info.free_bytes < min_free_bytes:
            critical = True
            messages.append(
                f"[CRITICAL] {info.mount_point}: 可用空间 {_format_bytes(info.free_bytes)} "
                f"< 最小要求 {_format_bytes(min_free_bytes)}"
            )

    ok = not critical and not warning

    return DiskCheckResult(
        ok=ok,
        warning=warning,
        critical=critical,
        message="; ".join(messages) if messages else "OK",
        disks=disk_infos,
    )


def check_space_for_upload(file_size_bytes: int) -> DiskCheckResult:
    """上传前检查磁盘空间。

    检查 data/ 分区是否有足够空间。
    """
    settings = get_settings()
    data_dir = str(settings.DATA_DIR)

    info = _get_disk_usage(data_dir)
    if info is None:
        return DiskCheckResult(
            ok=True,
            message="磁盘检查失败，跳过空间验证",
        )

    # 需要 2x 文件大小（原始 + 临时 + 索引）
    required = file_size_bytes * 2
    if info.free_bytes < required:
        return DiskCheckResult(
            ok=False,
            critical=True,
            message=(
                f"上传空间不足: 需要 {_format_bytes(required)}, "
                f"可用 {_format_bytes(info.free_bytes)}"
            ),
            disks=[info],
        )

    return DiskCheckResult(ok=True, message="空间充足", disks=[info])


def check_space_for_backup(estimated_size_bytes: int = 500 * 1024 * 1024) -> DiskCheckResult:
    """备份前检查磁盘空间。

    保守估计备份需要 ~500MB，实际大小取决于数据量。
    """
    settings = get_settings()
    backup_dir = str(settings.PROJECT_ROOT / "backups")

    info = _get_disk_usage(backup_dir)
    if info is None:
        return DiskCheckResult(
            ok=True,
            message="磁盘检查失败，跳过空间验证",
        )

    # 需要备份大小 + 20% margin
    required = int(estimated_size_bytes * 1.2)
    if info.free_bytes < required:
        return DiskCheckResult(
            ok=False,
            critical=True,
            message=(
                f"备份空间不足: 需要 {_format_bytes(required)}, "
                f"可用 {_format_bytes(info.free_bytes)}"
            ),
            disks=[info],
        )

    return DiskCheckResult(ok=True, message="备份空间充足", disks=[info])


def get_disk_summary() -> dict:
    """获取磁盘使用摘要（用于管理后台显示）。

    Returns
    -------
    dict
        {
            "status": "ok" | "warning" | "critical",
            "disks": [{path, total_gb, used_gb, free_gb, percent_used}],
            "message": str
        }
    """
    result = check_disk_space()
    disks_data = []
    for d in result.disks:
        disks_data.append({
            "path": d.path,
            "mount_point": d.mount_point,
            "total_gb": round(d.total_bytes / (1024 ** 3), 2),
            "used_gb": round(d.used_bytes / (1024 ** 3), 2),
            "free_gb": round(d.free_bytes / (1024 ** 3), 2),
            "percent_used": d.percent_used,
        })

    status = "ok"
    if result.critical:
        status = "critical"
    elif result.warning:
        status = "warning"

    return {
        "status": status,
        "disks": disks_data,
        "message": result.message,
    }


def _format_bytes(b: int) -> str:
    """格式化字节数为可读字符串。"""
    if b >= 1024 ** 3:
        return f"{b / (1024 ** 3):.1f} GB"
    elif b >= 1024 ** 2:
        return f"{b / (1024 ** 2):.1f} MB"
    elif b >= 1024:
        return f"{b / 1024:.1f} KB"
    else:
        return f"{b} B"
