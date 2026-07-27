"""聊天相关数据模型 — 请求与响应"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field, field_validator

from backend.app.config import get_settings


# ---------------------------------------------------------------------------
# 问答请求
# ---------------------------------------------------------------------------


class ChatRequest(BaseModel):
    """用户问答请求。"""

    question: str = Field(
        ...,
        description="用户问题",
        min_length=1,
        max_length=get_settings().MAX_QUESTION_LENGTH,
    )

    @field_validator("question", mode="after")
    @classmethod
    def sanitize_question(cls, v: str) -> str:
        """去除首尾空白，校验非空。"""
        if v is None:
            raise ValueError("问题不能为空")
        cleaned = v.strip()
        if not cleaned:
            raise ValueError("问题不能为空（仅含空白字符）")
        # 长度校验（pydantic max_length 已处理，此处做额外安全）
        max_len = get_settings().MAX_QUESTION_LENGTH
        if len(cleaned) > max_len:
            raise ValueError(f"问题长度不能超过 {max_len} 个字符")
        return cleaned


# ---------------------------------------------------------------------------
# 普通用户响应
# ---------------------------------------------------------------------------


class UserChatResponse(BaseModel):
    """普通用户问答响应 — 不得包含 sources。"""

    success: bool = Field(..., description="请求是否成功")
    answer: str = Field(..., description="回答文本")
    refused: bool = Field(..., description="是否拒答")
    refusal_reason: Optional[str] = Field(None, description="拒答原因")
    model_name: Optional[str] = Field(None, description="使用的模型名称（来自 AI 服务配置中心）")
    latency_seconds: Optional[float] = Field(None, description="响应耗时（秒）")
    request_id: str = Field(..., description="请求追踪 ID")


# ---------------------------------------------------------------------------
# 管理员来源
# ---------------------------------------------------------------------------


class SourceItem(BaseModel):
    """管理员可见的来源信息 — 经过裁剪，RAG 3.0 增强版。"""

    file_name: str = Field(..., description="来源文件名")
    version: Optional[str] = Field(None, description="文件版本")
    page: Optional[int] = Field(None, description="页码")
    content_preview: str = Field(..., description="原文片段预览")


class DebugResultItem(BaseModel):
    """检索调试结果 — 单条检索结果详情。"""

    rank: int = Field(..., description="排序")
    file_name: str = Field(..., description="来源文件名")
    chunk_id: Optional[str] = Field(None, description="分块 ID")
    content_preview: str = Field(..., description="内容预览")

    # 可选字段（不同阶段有不同字段）
    hybrid_score: Optional[float] = Field(None, description="混合检索融合分数")
    vector_score: Optional[float] = Field(None, description="向量检索分数")
    bm25_score: Optional[float] = Field(None, description="BM25 关键词分数")
    rerank_score: Optional[float] = Field(None, description="Reranker 重排序分数")
    version: Optional[str] = Field(None, description="文件版本")
    page: Optional[int] = Field(None, description="页码")


class DebugConfig(BaseModel):
    """检索调试 — 当前 RAG 配置。"""

    vector_weight: float = Field(..., description="向量检索权重")
    keyword_weight: float = Field(..., description="关键词检索权重")
    rerank_enabled: bool = Field(..., description="是否启用 Reranker")
    fetch_k: int = Field(..., description="检索召回数")
    rerank_top_k: int = Field(..., description="Reranker 输出数")
    max_raw_distance: Optional[float] = Field(None, description="L2 距离上限")
    min_relevance_score: Optional[float] = Field(None, description="相关度下限")


class DebugInfo(BaseModel):
    """检索调试信息 — 完整检索链路 (RAG 3.0 增强版)。"""

    query: str = Field(..., description="原始查询")
    query_rewrite: Optional[str] = Field(None, description="Query Rewrite 改写结果")
    retrieval_stats: Optional[dict] = Field(None, description="各阶段检索统计")
    initial_results: list[DebugResultItem] = Field(
        default_factory=list, description="Hybrid 混合检索结果"
    )
    reranked_results: Optional[list[DebugResultItem]] = Field(
        None, description="Reranker 重排序后结果"
    )
    final_results: list[DebugResultItem] = Field(
        default_factory=list, description="最终送入 LLM 的上下文"
    )
    refused: bool = Field(False, description="是否拒答")
    refusal_reason: Optional[str] = Field(None, description="拒答原因")
    config: Optional[DebugConfig] = Field(None, description="当前 RAG 配置")


class AdminChatResponse(UserChatResponse):
    """管理员问答响应 — 可以包含经过裁剪的来源列表和调试信息。"""

    sources: list[SourceItem] = Field(
        default_factory=list, description="来源列表（管理员可见）"
    )
    debug_info: Optional[DebugInfo] = Field(
        None, description="检索调试信息（开启调试模式时返回）"
    )


# ============================================================================
# 聊天历史 — 会话 & 消息
# ============================================================================


# --- 消息 ---

class MessageResponse(BaseModel):
    """单条消息响应。"""

    id: int = Field(..., description="消息 ID")
    session_id: int = Field(..., description="所属会话 ID")
    role: str = Field(..., description="消息角色: user / assistant")
    content: str = Field(..., description="消息内容")
    created_at: datetime = Field(..., description="创建时间（UTC）")

    model_config = {"from_attributes": True}


class MessageListResponse(BaseModel):
    """消息列表响应。"""

    success: bool = Field(default=True, description="请求是否成功")
    session_id: int = Field(..., description="会话 ID")
    messages: list[MessageResponse] = Field(
        default_factory=list, description="消息列表"
    )


# --- 会话 ---

class SessionResponse(BaseModel):
    """会话响应。"""

    id: int = Field(..., description="会话 ID")
    title: str = Field(..., description="会话标题")
    message_count: int = Field(default=0, description="消息数量")
    created_at: datetime = Field(..., description="创建时间（UTC）")
    updated_at: datetime = Field(..., description="更新时间（UTC）")

    model_config = {"from_attributes": True}


class SessionListResponse(BaseModel):
    """会话列表响应。"""

    success: bool = Field(default=True, description="请求是否成功")
    sessions: list[SessionResponse] = Field(
        default_factory=list, description="会话列表"
    )
    total: int = Field(default=0, description="会话总数")
    page: int = Field(default=1, description="当前页码")
    page_size: int = Field(default=20, description="每页数量")


class CreateSessionRequest(BaseModel):
    """创建会话请求。"""

    title: str = Field(
        default="新对话",
        description="会话标题",
        min_length=1,
        max_length=255,
    )


class CreateSessionResponse(BaseModel):
    """创建会话响应。"""

    success: bool = Field(default=True, description="请求是否成功")
    session: SessionResponse = Field(..., description="创建的会话")


class SendMessageRequest(BaseModel):
    """发送消息请求。"""

    session_id: int = Field(..., description="会话 ID", gt=0)
    question: str = Field(
        ...,
        description="用户问题",
        min_length=1,
        max_length=get_settings().MAX_QUESTION_LENGTH,
    )

    @field_validator("question", mode="after")
    @classmethod
    def sanitize_question(cls, v: str) -> str:
        """去除首尾空白。"""
        if v is None:
            raise ValueError("问题不能为空")
        cleaned = v.strip()
        if not cleaned:
            raise ValueError("问题不能为空")
        return cleaned


class SendMessageResponse(BaseModel):
    """发送消息响应 — 包含回答和消息记录。"""

    success: bool = Field(default=True, description="请求是否成功")
    answer: str = Field(..., description="回答文本")
    refused: bool = Field(..., description="是否拒答")
    refusal_reason: Optional[str] = Field(None, description="拒答原因")
    model_name: Optional[str] = Field(None, description="使用的模型名称（来自 AI 服务配置中心）")
    latency_seconds: Optional[float] = Field(None, description="响应耗时（秒）")
    request_id: str = Field(..., description="请求追踪 ID")
    user_message: MessageResponse = Field(..., description="用户消息")
    assistant_message: MessageResponse = Field(..., description="助手消息")


class DeleteSessionResponse(BaseModel):
    """删除会话响应。"""

    success: bool = Field(default=True, description="请求是否成功")
    message: str = Field(..., description="操作结果信息")
    session_id: int = Field(..., description="被删除的会话 ID")
