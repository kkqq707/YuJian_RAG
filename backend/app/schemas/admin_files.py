"""管理员知识库文件管理 — 请求与响应模型"""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


# ---------------------------------------------------------------------------
# 文件列表
# ---------------------------------------------------------------------------


class KnowledgeFileItem(BaseModel):
    """知识库文件条目。"""

    id: str = Field(..., description="文件唯一 ID")
    original_name: str = Field(..., description="原始文件名")
    stored_name: str = Field(..., description="存储文件名")
    file_type: str = Field(..., description="文件类型")
    file_size: int = Field(..., description="文件大小（字节）")
    file_hash: str = Field("", description="文件 SHA-256 哈希")
    source_type: str = Field(..., description="来源类型: builtin | upload")
    upload_status: str = Field(..., description="上传状态")
    index_status: str = Field(..., description="索引状态: pending | processing | indexed | failed | deleted")
    chunk_count: int = Field(0, description="切分片段数量")
    upload_time: Optional[str] = Field(None, description="上传时间")
    indexed_time: Optional[str] = Field(None, description="索引完成时间")
    error_message: Optional[str] = Field(None, description="错误信息")
    is_active: bool = Field(True, description="是否活跃")
    current_version: str = Field("v1", description="当前版本号")
    last_index_time: Optional[str] = Field(None, description="最后索引时间")
    preview_available: bool = Field(False, description="是否支持预览")

    model_config = ConfigDict(from_attributes=True)


class FileListResponse(BaseModel):
    """文件列表响应。"""

    success: bool = Field(True, description="请求是否成功")
    total: int = Field(..., description="文件总数")
    files: list[KnowledgeFileItem] = Field(default_factory=list, description="文件列表")


# ---------------------------------------------------------------------------
# 文件上传
# ---------------------------------------------------------------------------


class FileUploadResult(BaseModel):
    """单个文件上传结果。"""

    filename: str = Field(..., description="原始文件名")
    success: bool = Field(..., description="是否成功")
    file_id: Optional[str] = Field(None, description="文件 ID（成功时返回）")
    version: Optional[str] = Field(None, description="版本号")
    error: Optional[str] = Field(None, description="错误信息（失败时返回）")
    skipped: bool = Field(False, description="是否因已存在而跳过")


class FileUploadResponse(BaseModel):
    """文件上传响应。"""

    success: bool = Field(True, description="请求是否成功")
    message: str = Field(..., description="结果描述")
    total: int = Field(..., description="上传文件总数")
    succeeded: int = Field(0, description="成功数量")
    failed: int = Field(0, description="失败数量")
    skipped: int = Field(0, description="跳过数量（已存在）")
    results: list[FileUploadResult] = Field(default_factory=list, description="单个文件结果")


# ---------------------------------------------------------------------------
# 文件删除
# ---------------------------------------------------------------------------


class FileDeleteResponse(BaseModel):
    """文件删除响应。"""

    success: bool = Field(True, description="删除是否成功")
    message: str = Field(..., description="结果描述")
    file_id: str = Field(..., description="被删除的文件 ID")
    deleted_chunks: int = Field(0, description="从索引中删除的 chunk 数量")


# ---------------------------------------------------------------------------
# 重建索引
# ---------------------------------------------------------------------------


class RebuildIndexResponse(BaseModel):
    """重建索引响应。"""

    success: bool = Field(True, description="重建是否成功")
    message: str = Field(..., description="结果描述")
    total_files: int = Field(0, description="处理的文件总数")
    indexed: int = Field(0, description="成功索引的文件数")
    failed: int = Field(0, description="索引失败的文件数")
    total_chunks: int = Field(0, description="生成的总片段数")
    elapsed_seconds: float = Field(0.0, description="耗时（秒）")
    task_id: Optional[str] = Field(None, description="索引任务 ID（用于追踪进度）")
    errors: list[str] = Field(default_factory=list, description="失败文件的错误信息列表")
    error: Optional[str] = Field(None, description="整体错误信息（失败时返回）")


# ---------------------------------------------------------------------------
# 索引状态
# ---------------------------------------------------------------------------


class IndexStatusResponse(BaseModel):
    """索引状态响应。"""

    success: bool = Field(True, description="请求是否成功")
    chroma_status: str = Field(..., description="Chroma 状态: ok | error | not_found")
    total_vectors: int = Field(0, description="向量库中的向量总数")
    indexed_files: int = Field(0, description="已索引文件数")
    pending_files: int = Field(0, description="待索引文件数")
    total_chunks: int = Field(0, description="知识库总片段数")
    last_update_time: Optional[str] = Field(None, description="最后索引更新时间")
    embedding_model: str = Field("", description="Embedding 模型名称")
    chroma_collection: str = Field("", description="Chroma 集合名称")
    consistency_ok: bool = Field(True, description="数据库与 Chroma 状态是否一致")
    consistency_note: str = Field("", description="一致性说明")


# ---------------------------------------------------------------------------
# 文件详情
# ---------------------------------------------------------------------------


class FileVersionItem(BaseModel):
    """文件版本条目。"""

    id: str = Field(..., description="版本记录 ID")
    file_id: str = Field(..., description="所属文件 ID")
    version: str = Field(..., description="版本号: v1, v2, ...")
    file_hash: str = Field(..., description="该版本的 SHA-256 哈希")
    file_size: int = Field(..., description="该版本的文件大小")
    operator: str = Field("admin", description="操作者")
    created_time: str = Field(..., description="创建时间")
    change_type: str = Field("create", description="变更类型: create | update | rollback")
    stored_name: str = Field("", description="该版本存储文件名")


class FileDetailResponse(BaseModel):
    """文件详情响应（含版本历史）。"""

    success: bool = Field(True, description="请求是否成功")
    file: Optional[dict] = Field(None, description="文件详情（含版本列表）")
    message: Optional[str] = Field(None, description="错误信息（失败时返回）")


# ---------------------------------------------------------------------------
# 文件内容预览
# ---------------------------------------------------------------------------


class FileContentResponse(BaseModel):
    """文件内容预览响应（分页）。"""

    success: bool = Field(True, description="请求是否成功")
    content: str = Field("", description="当前页文本内容")
    page: int = Field(1, description="当前页码")
    page_size: int = Field(10000, description="每页字符数")
    total_chars: int = Field(0, description="文件总字符数")
    total_pages: int = Field(1, description="总页数")
    file_type: str = Field("", description="文件类型")
    chunks_preview: list[str] = Field(default_factory=list, description="前5个chunk预览")
    message: Optional[str] = Field(None, description="错误信息（失败时返回）")


# ---------------------------------------------------------------------------
# 版本管理
# ---------------------------------------------------------------------------


class VersionActionResponse(BaseModel):
    """版本操作响应（删除/恢复）。"""

    success: bool = Field(True, description="操作是否成功")
    message: str = Field(..., description="结果描述")
    was_current: bool = Field(False, description="（删除时）是否影响了当前版本")
    current_version: Optional[str] = Field(None, description="（恢复时）新的当前版本")


# ---------------------------------------------------------------------------
# 操作日志
# ---------------------------------------------------------------------------


class OperationLogItem(BaseModel):
    """操作日志条目。"""

    id: str = Field(..., description="日志 ID")
    user_id: str = Field("admin", description="用户 ID")
    operation: str = Field(..., description="操作类型")
    target: str = Field(..., description="操作目标")
    time: str = Field(..., description="操作时间")
    result: str = Field("success", description="操作结果")


class OperationLogsResponse(BaseModel):
    """操作日志列表响应。"""

    success: bool = Field(True, description="请求是否成功")
    total: int = Field(0, description="日志总数")
    logs: list[OperationLogItem] = Field(default_factory=list, description="日志列表")


# ---------------------------------------------------------------------------
# 通用
# ---------------------------------------------------------------------------


class SingleFileIndexResponse(BaseModel):
    """单文件索引响应。"""

    success: bool = Field(True, description="索引是否成功")
    message: str = Field(..., description="结果描述")
    chunk_count: int = Field(0, description="生成的 chunk 数量")


class FileErrorResponse(BaseModel):
    """文件操作错误响应。"""

    success: bool = Field(False, description="请求是否成功")
    error: dict = Field(..., description="错误详情")
