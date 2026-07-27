"""系统状态相关数据模型"""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    """健康检查响应 — 生产级多维度检测。"""

    status: str = Field("healthy", description="整体状态: healthy | unhealthy")
    backend: bool = Field(True, description="FastAPI 服务是否运行")
    database: bool = Field(True, description="SQLite 数据库连接是否正常")
    rag: bool = Field(True, description="RAG 向量库连接是否正常")
    timestamp: str = Field("", description="检查时间戳 (ISO 8601)")


class SystemStatusResponse(BaseModel):
    """系统状态响应 — 不含 API Key / 绝对路径 / 环境变量。"""

    status: str = Field(..., description="整体状态")
    vector_store: str = Field(..., description="向量库状态: ok | not_found | error")
    knowledge_chunks: int = Field(0, description="知识库片段数量")
    knowledge_files: int = Field(0, description="知识库文件数量")
    enterprise_name: str = Field("企业智库 AI", description="企业名称")
    llm_configured: bool = Field(False, description="LLM 是否已配置")
    llm_provider: Optional[str] = Field(None, description="LLM 提供商")
    model_name: Optional[str] = Field(None, description="当前使用的模型名称（来自 AI 服务配置中心）")


# ---------------------------------------------------------------------------
# RAG 健康检查
# ---------------------------------------------------------------------------


class ChromaHealthInfo(BaseModel):
    """Chroma 向量库健康信息。"""

    collections: int = Field(0, description="集合数量")
    vectors: int = Field(0, description="向量总数")
    status: str = Field("not_found", description="状态: ok | not_found | collection_not_found | error")
    error: Optional[str] = Field(None, description="错误信息（仅在 status=error 时）")


class DocumentsHealthInfo(BaseModel):
    """文档健康信息。"""

    total: int = Field(0, description="文档总数")
    indexed: int = Field(0, description="已索引文档数")
    failed: int = Field(0, description="索引失败文档数")
    pending: int = Field(0, description="待处理文档数")
    last_update_time: Optional[str] = Field(None, description="最后索引更新时间")


class EmbeddingHealthInfo(BaseModel):
    """Embedding 模型健康信息。"""

    model: str = Field("", description="模型名称")
    loaded: bool = Field(False, description="模型是否已加载")
    model_path: str = Field("", description="模型本地路径")
    load_method: str = Field("", description="加载方式")


class IndexTaskInfo(BaseModel):
    """索引任务信息。"""

    id: Optional[str] = Field(None, description="任务 ID")
    status: Optional[str] = Field(None, description="任务状态")
    progress: int = Field(0, description="进度百分比")
    total_files: int = Field(0, description="总文件数")
    success_count: int = Field(0, description="成功数")
    failed_count: int = Field(0, description="失败数")
    total_chunks: int = Field(0, description="总片段数")
    start_time: Optional[str] = Field(None, description="开始时间")
    end_time: Optional[str] = Field(None, description="结束时间")


class BackupHealthInfo(BaseModel):
    """备份健康信息。"""

    last_backup_time: Optional[str] = Field(None, description="最后备份时间")
    last_backup_size_bytes: int = Field(0, description="最后备份大小（字节）")
    last_backup_file: Optional[str] = Field(None, description="最后备份文件名")
    total_backups: int = Field(0, description="备份总数")
    total_backups_size_bytes: int = Field(0, description="备份总大小（字节）")
    status: str = Field("no_backup", description="备份状态: ok | no_backup")


class RAGHealthResponse(BaseModel):
    """RAG 完整健康检查响应。"""

    status: str = Field("healthy", description="整体状态: healthy | degraded | unhealthy")
    chroma: ChromaHealthInfo = Field(default_factory=ChromaHealthInfo, description="Chroma 向量库状态")
    documents: DocumentsHealthInfo = Field(default_factory=DocumentsHealthInfo, description="文档状态")
    embedding: EmbeddingHealthInfo = Field(default_factory=EmbeddingHealthInfo, description="Embedding 模型状态")
    last_index_task: Optional[IndexTaskInfo] = Field(None, description="最近索引任务")
    last_index_time: Optional[str] = Field(None, description="最后索引时间")
    backup: BackupHealthInfo = Field(default_factory=BackupHealthInfo, description="备份状态")


# ---------------------------------------------------------------------------
# 模型健康检查
# ---------------------------------------------------------------------------


class ModelHealthInfo(BaseModel):
    """单个模型的健康信息。"""

    name: str = Field("", description="模型名称")
    loaded: bool = Field(False, description="模型是否已加载")
    path: str = Field("", description="模型本地路径")
    load_mode: str = Field("", description="加载模式: local / not_found / error")


class ModelHealthResponse(BaseModel):
    """模型健康检查响应。"""

    embedding: ModelHealthInfo = Field(default_factory=ModelHealthInfo, description="Embedding 模型状态")
    reranker: ModelHealthInfo = Field(default_factory=ModelHealthInfo, description="Reranker 模型状态")
