"""文件上传流式处理与安全校验 (Phase 8)

提供:
- 流式分块写入磁盘（不一次性读入内存）
- 文件名与路径安全处理
- MIME 类型和文件签名校验
- SHA-256 流式计算
- 上传并发控制
- 临时文件原子重命名
"""

from __future__ import annotations

import asyncio
import hashlib
import logging
import os
import re
import uuid
from pathlib import Path
from typing import Optional

from fastapi import UploadFile

from backend.app.config import get_settings

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# 常量
# ---------------------------------------------------------------------------

# 允许的文件扩展名和对应 MIME 类型
ALLOWED_EXTENSIONS: set[str] = {".txt", ".md", ".pdf", ".docx", ".xlsx"}
ALLOWED_MIME_TYPES: dict[str, list[str]] = {
    ".txt": ["text/plain", "text/markdown"],
    ".md": ["text/plain", "text/markdown", "text/x-markdown"],
    ".pdf": ["application/pdf"],
    ".docx": ["application/vnd.openxmlformats-officedocument.wordprocessingml.document"],
    ".xlsx": ["application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"],
}

# 文件签名
FILE_SIGNATURES: dict[bytes, str] = {
    b"\x25\x50\x44\x46": ".pdf",
    b"\x50\x4b\x03\x04": ".docx",  # also xlsx
}

# 文件名安全模式
SAFE_FILENAME_PATTERN = re.compile(r"[^a-zA-Z0-9_\-.一-鿿\(\)（） ]")
MAX_FILENAME_LENGTH = 200
MAX_ORIGINAL_FILENAME_LENGTH = 255

# 危险路径模式
DANGEROUS_PATTERNS = [
    "..", "/", "\\", "\x00",
]

# 错误代码
ERR_FILE_TOO_LARGE = "FILE_TOO_LARGE"
ERR_UNSUPPORTED_FILE_TYPE = "UNSUPPORTED_FILE_TYPE"
ERR_EMPTY_FILE = "EMPTY_FILE"
ERR_INVALID_FILE_CONTENT = "INVALID_FILE_CONTENT"
ERR_DUPLICATE_DOCUMENT = "DUPLICATE_DOCUMENT"
ERR_PATH_TRAVERSAL = "PATH_TRAVERSAL"
ERR_UPLOAD_BUSY = "UPLOAD_BUSY"


# ---------------------------------------------------------------------------
# 文件名校验
# ---------------------------------------------------------------------------


def validate_safe_filename(filename: str) -> str:
    """验证并清理文件名，防止路径穿越和注入。

    Returns 清理后的安全文件名。Raises ValueError 如果不安全。
    """
    if not filename or not filename.strip():
        raise ValueError("文件名为空")

    name = filename.strip()

    # 检查危险模式
    for pattern in DANGEROUS_PATTERNS:
        if pattern in name:
            raise ValueError(f"文件名包含非法字符")

    # Windows 盘符检查
    if len(name) >= 2 and name[1] == ":":
        raise ValueError("文件名不能包含盘符")

    # 长度检查
    if len(name) > MAX_ORIGINAL_FILENAME_LENGTH:
        raise ValueError(f"文件名过长（{len(name)} 字符）")

    return name


def sanitize_display_name(filename: str) -> str:
    """生成安全的展示用文件名。"""
    name = Path(filename).stem
    suffix = Path(filename).suffix.lower()
    safe = SAFE_FILENAME_PATTERN.sub("_", name)
    safe = re.sub(r"_+", "_", safe).strip("_")
    if not safe:
        safe = "unnamed"
    max_len = MAX_FILENAME_LENGTH - len(suffix) - 1
    if len(safe) > max_len:
        safe = safe[:max_len]
    return safe + suffix


def generate_stored_filename(file_id: str, extension: str) -> str:
    """生成服务端存储文件名: {file_id}.{ext}"""
    ext = extension.lstrip(".")
    return f"{file_id}.{ext}"


def validate_extension(filename: str) -> str:
    """验证文件扩展名，返回小写扩展名（含点号）。Raises ValueError。"""
    ext = Path(filename).suffix.lower()
    if not ext:
        raise ValueError(ERR_UNSUPPORTED_FILE_TYPE + ": 无法识别文件类型")
    if ext not in ALLOWED_EXTENSIONS:
        raise ValueError(
            f"{ERR_UNSUPPORTED_FILE_TYPE}: 不支持 '{ext}'，当前支持: "
            f"{', '.join(sorted(ALLOWED_EXTENSIONS))}"
        )
    return ext


def validate_mime_for_extension(content_start: bytes, extension: str) -> None:
    """验证文件内容头部是否与扩展名一致。Raises ValueError。"""
    if len(content_start) < 4:
        # 文件太短，跳过签名检查
        return

    for signature, expected_ext in FILE_SIGNATURES.items():
        if extension == expected_ext:
            if not content_start.startswith(signature):
                raise ValueError(
                    f"{ERR_INVALID_FILE_CONTENT}: 文件签名不匹配，"
                    f"扩展名 {extension} 但内容不符合该格式"
                )


# ---------------------------------------------------------------------------
# SHA-256 流式计算
# ---------------------------------------------------------------------------


def compute_file_hash_streaming(file_path: Path) -> str:
    """流式计算文件 SHA-256（不一次读入内存）。"""
    sha256 = hashlib.sha256()
    with open(file_path, "rb") as f:
        chunk_size = get_settings().UPLOAD_CHUNK_SIZE_BYTES
        for chunk in iter(lambda: f.read(chunk_size), b""):
            sha256.update(chunk)
    return sha256.hexdigest()


# ---------------------------------------------------------------------------
# 流式上传
# ---------------------------------------------------------------------------


async def stream_upload_to_disk(
    file: UploadFile,
    upload_dir: Path,
    *,
    upload_semaphore: asyncio.Semaphore | None = None,
) -> dict:
    """流式上传单个文件到磁盘。

    流程:
    1. 获取上传信号量（并发控制）
    2. 校验文件名和扩展名
    3. 分块读取并写入临时文件
    4. 实时统计已读字节数，超限立即终止
    5. 校验文件签名
    6. 计算 SHA-256
    7. 原子重命名临时文件

    Returns:
        {
            "success": bool,
            "document_id": str | None,
            "original_name": str,
            "stored_name": str,
            "stored_path": str (relative),
            "file_size": int,
            "file_hash": str,
            "file_type": str,
            "error": str | None,
            "error_code": str | None,
        }
    """
    settings = get_settings()
    original_name = file.filename or "unknown"
    result = {
        "success": False,
        "document_id": None,
        "original_name": original_name,
        "stored_name": "",
        "stored_path": "",
        "file_size": 0,
        "file_hash": "",
        "file_type": "",
        "error": None,
        "error_code": None,
    }

    # 上传并发控制
    acquired_semaphore = False
    if upload_semaphore:
        try:
            await asyncio.wait_for(upload_semaphore.acquire(), timeout=30.0)
            acquired_semaphore = True
        except asyncio.TimeoutError:
            result["error"] = "上传请求过多，请稍后重试"
            result["error_code"] = ERR_UPLOAD_BUSY
            return result

    tmp_path = None
    final_path = None

    try:
        # ---- 1. 校验文件名 ----
        safe_original = validate_safe_filename(original_name)

        # ---- 2. 校验扩展名 ----
        extension = validate_extension(safe_original)

        # ---- 3. 准备文件路径 ----
        upload_dir.mkdir(parents=True, exist_ok=True)
        doc_id = str(uuid.uuid4())
        stored_name = generate_stored_filename(doc_id, extension)
        relative_path = stored_name  # 仅存储文件名，不暴露绝对路径
        final_path = upload_dir / stored_name

        # 临时文件名（写入完成后原子重命名）
        tmp_name = f".tmp_{doc_id}_{stored_name}"
        tmp_path = upload_dir / tmp_name

        # ---- 4. 流式分块写入 ----
        sha256 = hashlib.sha256()
        total_bytes = 0
        max_bytes = settings.MAX_UPLOAD_SIZE_BYTES
        chunk_size = settings.UPLOAD_CHUNK_SIZE_BYTES

        # Content-Length 作为快速前置检查（可选，不完全信任）
        # 客户端可能不发送 Content-Length

        # 在线程池中执行文件写入（避免阻塞事件循环）
        loop = asyncio.get_event_loop()

        def _write_chunk(data: bytes, mode: str = "ab"):
            with open(tmp_path, mode) as f:
                f.write(data)

        while True:
            chunk = await file.read(chunk_size)
            if not chunk:
                break

            total_bytes += len(chunk)
            sha256.update(chunk)

            # 超限检查
            if total_bytes > max_bytes:
                raise ValueError(
                    f"{ERR_FILE_TOO_LARGE}: 文件大小超过 {settings.MAX_UPLOAD_SIZE_MB}MB 限制"
                )

            # 在线程池中写入文件块
            await loop.run_in_executor(None, _write_chunk, chunk)

        # ---- 5. 空文件检查 ----
        if total_bytes == 0:
            raise ValueError(f"{ERR_EMPTY_FILE}: 文件为空")

        file_hash = sha256.hexdigest()

        # ---- 6. 文件签名校验 ----
        # 读取前 4 字节用于签名检查
        def _read_head():
            with open(tmp_path, "rb") as f:
                return f.read(4)

        head = await loop.run_in_executor(None, _read_head)
        validate_mime_for_extension(head, extension)

        # ---- 7. 原子重命名 ----
        def _rename():
            if final_path.exists():
                final_path.unlink()
            os.replace(tmp_path, final_path)

        await loop.run_in_executor(None, _rename)
        tmp_path = None  # 已重命名，不再需要清理

        # ---- 8. 构建结果 ----
        result["success"] = True
        result["document_id"] = doc_id
        result["stored_name"] = stored_name
        result["stored_path"] = relative_path
        result["file_size"] = total_bytes
        result["file_hash"] = file_hash
        result["file_type"] = extension

        logger.info(
            "文件流式上传成功: %s → %s (size=%d, hash=%s)",
            original_name, stored_name, total_bytes, file_hash[:16],
        )
        return result

    except ValueError as e:
        error_str = str(e)
        result["error"] = error_str[:300]

        # 提取错误代码
        for code in [ERR_FILE_TOO_LARGE, ERR_UNSUPPORTED_FILE_TYPE,
                      ERR_EMPTY_FILE, ERR_INVALID_FILE_CONTENT,
                      ERR_PATH_TRAVERSAL, ERR_UPLOAD_BUSY, ERR_DUPLICATE_DOCUMENT]:
            if error_str.startswith(code):
                result["error_code"] = code
                break
        if not result["error_code"]:
            result["error_code"] = ERR_INVALID_FILE_CONTENT

        logger.warning("文件上传校验失败: %s — %s", original_name, error_str[:200])
        return result

    except Exception as e:
        result["error"] = str(e).split("\n")[0][:300]
        result["error_code"] = ERR_INVALID_FILE_CONTENT
        logger.exception("文件上传异常: %s", original_name)
        return result

    finally:
        # 清理临时文件
        if tmp_path and tmp_path.exists():
            try:
                tmp_path.unlink()
            except Exception:
                pass

        # 如果上传失败，清理已写入的最终文件
        if not result["success"] and final_path and final_path.exists():
            try:
                final_path.unlink()
            except Exception:
                pass

        # 释放上传信号量
        if acquired_semaphore and upload_semaphore:
            upload_semaphore.release()


# ---------------------------------------------------------------------------
# 重复文件检测
# ---------------------------------------------------------------------------


def check_duplicate_file(
    file_hash: str,
    file_size: int,
    upload_dir: Path,
) -> Optional[dict]:
    """检查文件是否已存在（在企业公共知识库范围内）。

    Returns 已存在文件的记录，或 None。
    """
    from src.knowledge_manager import get_file_by_hash

    existing = get_file_by_hash(file_hash)
    if existing and existing.get("is_active"):
        return existing
    return None


# ---------------------------------------------------------------------------
# 路径安全验证
# ---------------------------------------------------------------------------


def validate_path_in_upload_dir(file_path: Path, upload_dir: Path) -> bool:
    """验证文件路径在 upload 目录内（防止路径穿越）。"""
    try:
        resolved = file_path.resolve()
        upload_resolved = upload_dir.resolve()
        return str(resolved).startswith(str(upload_resolved))
    except Exception:
        return False
