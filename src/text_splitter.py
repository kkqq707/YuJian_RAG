"""企业知识库中文文本切分器

基于 RecursiveCharacterTextSplitter，优先按自然段、中文标点切分。
chunk_id 稳定可复现，支持完全重复片段去重。
"""

from __future__ import annotations

import hashlib
import logging
import re
from typing import List

from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter

from src.config import CHUNK_SIZE, CHUNK_OVERLAP

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# 中文分隔符优先级（从上到下依次尝试）
# ---------------------------------------------------------------------------
_CHINESE_SEPARATORS = [
    "\n\n",
    "\n",
    "。",
    "！",
    "？",
    "；",
    "：",
    "，",
    "、",
    " ",
    "",
]

# ---------------------------------------------------------------------------
# 参数校验
# ---------------------------------------------------------------------------


def _validate_chunk_config() -> None:
    """校验切分配置合法性，非法时抛出中文异常。"""
    if CHUNK_SIZE <= 0:
        raise ValueError(f"chunk_size 必须大于 0，当前值: {CHUNK_SIZE}")
    if CHUNK_OVERLAP < 0:
        raise ValueError(f"chunk_overlap 不能为负数，当前值: {CHUNK_OVERLAP}")
    if CHUNK_OVERLAP >= CHUNK_SIZE:
        raise ValueError(
            f"chunk_overlap ({CHUNK_OVERLAP}) 必须小于 chunk_size ({CHUNK_SIZE})"
        )


# ---------------------------------------------------------------------------
# 公开函数
# ---------------------------------------------------------------------------


def create_text_splitter() -> RecursiveCharacterTextSplitter:
    """创建针对中文优化的递归文本切分器。

    Returns
    -------
    RecursiveCharacterTextSplitter
    """
    _validate_chunk_config()
    return RecursiveCharacterTextSplitter(
        chunk_size=CHUNK_SIZE,
        chunk_overlap=CHUNK_OVERLAP,
        separators=_CHINESE_SEPARATORS,
        keep_separator=True,
        strip_whitespace=False,
        length_function=len,
        is_separator_regex=False,
    )


def split_documents(documents: list[Document]) -> list[Document]:
    """对 Document 列表执行中文切分，为每个 chunk 附加完整 metadata。

    Parameters
    ----------
    documents : list[Document]
        原始文档列表（通常来自 document_loader）

    Returns
    -------
    list[Document]
        切分后的 Document 列表，按原始顺序排列
    """
    if not documents:
        return []

    _validate_chunk_config()
    splitter = create_text_splitter()

    all_chunks: list[Document] = []
    for doc in documents:
        parent_id = doc.metadata.get("document_id", "unknown")
        parent_page = doc.metadata.get("page", 1)
        chunks = splitter.split_documents([doc])

        # 为每个 chunk 附加切分 metadata
        for idx, chunk in enumerate(chunks, start=1):
            cleaned = _clean_chunk(chunk.page_content)
            if not cleaned:
                continue

            chunk.page_content = cleaned
            chunk_char_count = len(cleaned)
            chunk_hash = _compute_hash(cleaned)
            chunk_id = _make_chunk_id(parent_id, parent_page, idx)

            # 保留原始 metadata + 新增切分 metadata
            chunk.metadata = {
                **doc.metadata,
                "chunk_id": chunk_id,
                "chunk_index": idx,
                "chunk_char_count": chunk_char_count,
                "chunk_hash": chunk_hash,
                "parent_document_id": parent_id,
            }
            all_chunks.append(chunk)

    return all_chunks


def deduplicate_chunks(documents: list[Document]) -> list[Document]:
    """去除完全重复的 chunk（基于规范化后的 page_content 哈希）。

    保留首次出现，不做模糊去重或语义合并。

    Parameters
    ----------
    documents : list[Document]

    Returns
    -------
    list[Document]
    """
    if not documents:
        return []

    seen: set[str] = set()
    unique: list[Document] = []

    before = len(documents)
    for doc in documents:
        norm = _normalize_for_dedup(doc.page_content)
        if norm not in seen:
            seen.add(norm)
            unique.append(doc)

    after = len(unique)
    if before != after:
        logger.info("去重: %d → %d chunks（移除 %d 个完全重复）", before, after, before - after)

    # 事后检查 chunk_id 唯一性
    chunk_ids = [d.metadata.get("chunk_id", "") for d in unique]
    if len(chunk_ids) != len(set(chunk_ids)):
        logger.warning("去重后存在重复 chunk_id，请检查输入数据")

    return unique


# ---------------------------------------------------------------------------
# 内部辅助
# ---------------------------------------------------------------------------


def _clean_chunk(text: str) -> str:
    """轻量清理：去除首尾空白，压缩连续 3+ 空行为最多 2 个换行。"""
    t = text.strip()
    # 连续 3 个以上空行 → 最多保留 2 个换行
    t = re.sub(r"\n{3,}", "\n\n", t)
    return t


def _normalize_for_dedup(text: str) -> str:
    """规范化文本用于完全重复判定（去除所有空白序列差异）。"""
    return re.sub(r"\s+", " ", text).strip()


def _compute_hash(text: str) -> str:
    """计算文本的 SHA-256 前 16 位（稳定哈希）。"""
    return hashlib.sha256(text.encode("utf-8", errors="replace")).hexdigest()[:16]


def _make_chunk_id(parent_document_id: str, page: int, chunk_index: int) -> str:
    """生成稳定 chunk_id。

    示例: 公司信息_txt_page_0001_chunk_0003
    """
    page = max(page, 1)
    return f"{parent_document_id}_page_{page:04d}_chunk_{chunk_index:04d}"
