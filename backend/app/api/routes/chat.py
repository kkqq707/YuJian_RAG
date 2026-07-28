"""问答路由 — 普通用户聊天 & 管理员预览 & 聊天历史管理

权限:
- POST /api/v1/chat: 需要登录（admin / user 均可访问）
- POST /api/v1/admin/chat-preview: 需要管理员权限
- GET/POST/DELETE /api/v1/chat/sessions: 需要登录（用户隔离）
- GET /api/v1/chat/sessions/{id}/messages: 需要登录（用户隔离）
- POST /api/v1/chat/message: 需要登录（发送消息并保存）
"""

from __future__ import annotations

import logging
import time
import uuid

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from backend.app.database import get_db
from backend.app.models.user import User
from backend.app.repositories import chat_repository
from backend.app.schemas.chat import (
    AdminChatResponse,
    ChatRequest,
    ClearSessionResponse,
    CreateSessionRequest,
    CreateSessionResponse,
    DebugConfig,
    DebugInfo,
    DebugResultItem,
    DeleteMessageResponse,
    DeleteSessionResponse,
    MessageFeedbackRequest,
    MessageFeedbackResponse,
    MessageListResponse,
    MessageResponse,
    SendMessageRequest,
    SendMessageResponse,
    SessionListResponse,
    SessionResponse,
    SourceItem,
    UpdateSessionTitleRequest,
    UpdateSessionTitleResponse,
    UserChatResponse,
)
from backend.app.security.dependencies import get_current_active_user, require_admin, require_normal_user
from backend.app.services.rag_adapter import get_rag_adapter

logger = logging.getLogger(__name__)

router = APIRouter(tags=["问答"])


@router.post("/chat", response_model=UserChatResponse)
async def chat(
    request: Request,
    body: ChatRequest,
    current_user: User = Depends(require_normal_user),
    db: Session = Depends(get_db),
):
    """普通用户问答 — 不返回 sources / chunk_id / raw_distance / relevance_score。

    需要普通用户权限，管理员禁止访问。
    知识库外问题保持原有拒答逻辑。
    LLM 使用普通用户 Prompt（隐藏来源、简洁回答 300-500 字）。

    消息自动保存到 chat_messages，便于工作台统计今日问答。
    """
    request_id = getattr(request.state, "request_id", str(uuid.uuid4()))
    t0 = time.perf_counter()

    adapter = get_rag_adapter()
    result = adapter.ask_user(body.question)

    latency = round(time.perf_counter() - t0, 3)

    # 自动创建会话并保存消息（用于工作台统计）
    try:
        title = body.question.strip()[:24].replace("\n", " ")
        if len(body.question.strip()) > 24:
            title += "..."
        session = chat_repository.create_session(db, current_user.id, title=title)
        chat_repository.create_message(
            db, session.id, role="user", content=body.question
        )
        chat_repository.create_message(
            db, session.id, role="assistant", content=result.answer
        )
    except Exception:
        logger.warning("自动保存消息失败，不影响主流程", exc_info=True)

    logger.info(
        "chat | user=%s | role=%s | question_len=%d | refused=%s | latency=%.3fs | request_id=%s",
        current_user.username,
        current_user.role,
        len(body.question),
        result.refused,
        latency,
        request_id,
    )

    return UserChatResponse(
        success=True,
        answer=result.answer,
        refused=result.refused,
        refusal_reason=result.refusal_reason,
        model_name=result.model,
        latency_seconds=latency,
        request_id=request_id,
    )


@router.post("/admin/chat-preview", response_model=AdminChatResponse)
async def admin_chat_preview(
    request: Request,
    body: ChatRequest,
    current_user: User = Depends(require_admin),
    debug: bool = False,
    db: Session = Depends(get_db),
):
    """管理员问答预览 — 可以返回经过裁剪的来源和检索调试信息。

    需要管理员权限（require_admin）。
    普通用户访问返回 403。

    RAG 3.0 增强:
    - LLM 使用管理员 Prompt（允许引用来源、详细回答）。
    - 来源包含: file_name, version, page, content_preview
    - debug=True 时返回完整检索链路（初始检索→Rerank→最终结果）
    - debug=True 时消息标记为 is_test，工作台统计排除

    Query Parameters
    ----------------
    debug : bool
        是否开启检索调试模式，默认 False。
        开启后返回完整的检索链路信息，方便调优。
    """
    request_id = getattr(request.state, "request_id", str(uuid.uuid4()))
    t0 = time.perf_counter()

    adapter = get_rag_adapter()
    result = adapter.ask_admin(body.question, debug=debug)

    latency = round(time.perf_counter() - t0, 3)

    # 自动保存消息（用于工作台统计；debug 模式标记为测试数据）
    try:
        title = body.question.strip()[:24].replace("\n", " ")
        if len(body.question.strip()) > 24:
            title += "..."
        session = chat_repository.create_session(db, current_user.id, title=title)
        chat_repository.create_message(
            db, session.id, role="user", content=body.question,
            is_test=debug,
        )
        chat_repository.create_message(
            db, session.id, role="assistant", content=result.answer,
            is_test=debug,
        )
    except Exception:
        logger.warning("自动保存消息失败，不影响主流程", exc_info=True)

    logger.info(
        "admin_chat_preview | user=%s | question_len=%d | refused=%s | "
        "sources=%d | debug=%s | latency=%.3fs | request_id=%s",
        current_user.username,
        len(body.question),
        result.refused,
        len(result.sources),
        debug,
        latency,
        request_id,
    )

    sources = [
        SourceItem(
            file_name=s.file_name,
            version=s.version,
            page=s.page,
            content_preview=s.content_preview,
        )
        for s in result.sources
    ]

    # 构建调试信息
    debug_info = None
    if debug and result.debug_info:
        debug_info = _build_debug_response(result.debug_info)

    return AdminChatResponse(
        success=True,
        answer=result.answer,
        refused=result.refused,
        refusal_reason=result.refusal_reason,
        model_name=result.model,
        latency_seconds=latency,
        request_id=request_id,
        sources=sources,
        debug_info=debug_info,
    )


# ============================================================================
# 聊天历史管理
# ============================================================================


@router.get("/chat/sessions", response_model=SessionListResponse)
async def list_sessions(
    page: int = 1,
    page_size: int = 20,
    current_user: User = Depends(require_normal_user),
    db: Session = Depends(get_db),
):
    """获取当前用户的聊天会话（分页）。

    按更新时间降序排列，仅返回属于当前用户的会话。
    默认每页 20 条，启动时仅加载最近会话，不加载全部历史。
    """
    sessions = chat_repository.get_user_sessions(
        db, current_user.id, page=page, page_size=page_size
    )
    total = chat_repository.get_user_sessions_count(db, current_user.id)

    result: list[SessionResponse] = []
    for s in sessions:
        msg_count = chat_repository.get_message_count(db, s.id)
        result.append(SessionResponse(
            id=s.id,
            title=s.title,
            message_count=msg_count,
            created_at=s.created_at,
            updated_at=s.updated_at,
        ))

    return SessionListResponse(
        success=True,
        sessions=result,
        total=total,
        page=page,
        page_size=page_size,
    )


@router.post("/chat/sessions", response_model=CreateSessionResponse)
async def create_session_handler(
    body: CreateSessionRequest,
    current_user: User = Depends(require_normal_user),
    db: Session = Depends(get_db),
):
    """创建新的聊天会话。

    会话归属于当前用户。
    """
    session = chat_repository.create_session(
        db, current_user.id, title=body.title
    )

    return CreateSessionResponse(
        success=True,
        session=SessionResponse(
            id=session.id,
            title=session.title,
            message_count=0,
            created_at=session.created_at,
            updated_at=session.updated_at,
        ),
    )


@router.get("/chat/sessions/{session_id}/messages", response_model=MessageListResponse)
async def get_session_messages_handler(
    session_id: int,
    current_user: User = Depends(require_normal_user),
    db: Session = Depends(get_db),
):
    """获取指定会话的所有消息。

    只能访问自己的会话消息，按创建时间升序排列。
    """
    messages = chat_repository.get_session_messages(
        db, session_id, current_user.id
    )

    if messages is None:
        raise HTTPException(
            status_code=404,
            detail="会话不存在或无权访问",
        )

    result = [
        MessageResponse(
            id=m.id,
            session_id=m.session_id,
            role=m.role,
            content=m.content,
            created_at=m.created_at,
        )
        for m in messages
    ]

    return MessageListResponse(
        success=True,
        session_id=session_id,
        messages=result,
    )


@router.post("/chat/message", response_model=SendMessageResponse)
async def send_message(
    request: Request,
    body: SendMessageRequest,
    current_user: User = Depends(require_normal_user),
    db: Session = Depends(get_db),
):
    """发送消息并保存到数据库。

    1. 验证会话所有权
    2. 保存用户消息到数据库
    3. 调用 RAG 生成回答
    4. 保存助手消息到数据库
    5. 更新会话 updated_at
    """
    request_id = getattr(request.state, "request_id", str(uuid.uuid4()))

    # 验证会话所有权
    session = chat_repository.get_session_by_id(
        db, body.session_id, current_user.id
    )
    if session is None:
        raise HTTPException(
            status_code=404,
            detail="会话不存在或无权访问",
        )

    # 保存用户消息
    user_msg = chat_repository.create_message(
        db, body.session_id, role="user", content=body.question
    )

    # Phase 6: 多轮对话记忆 — 获取历史消息并增强查询
    recent_messages = chat_repository.get_session_messages(
        db, body.session_id, current_user.id
    )
    # 排除刚保存的用户消息
    history_messages = [
        {"role": m.role, "content": m.content}
        for m in (recent_messages or [])[:-1]
    ] if recent_messages else []

    enhanced_question = body.question
    history_context = None
    if history_messages:
        try:
            import sys
            from pathlib import Path
            settings = __import__('backend.app.config', fromlist=['get_settings']).get_settings()
            if str(settings.PROJECT_ROOT) not in sys.path:
                sys.path.insert(0, str(settings.PROJECT_ROOT))
            from src.conversation_memory import get_conversation_memory
            memory = get_conversation_memory()
            enhanced_question = memory.get_contextualized_question(
                history_messages, body.question
            )
            history_context = memory.format_history_context(
                history_messages, body.question
            )
            logger.debug("Conversation Memory: '%s' → '%s'", body.question, enhanced_question)
        except Exception as e:
            logger.debug("Conversation Memory 跳过: %s", str(e)[:80])

    # 调用 RAG（普通用户模式，使用增强后的查询）
    t0 = time.perf_counter()
    adapter = get_rag_adapter()
    result = adapter.ask_user(enhanced_question)
    latency = round(time.perf_counter() - t0, 3)

    # 保存助手消息
    assistant_msg = chat_repository.create_message(
        db, body.session_id, role="assistant", content=result.answer
    )

    # 更新会话时间
    import datetime as dt
    session.updated_at = dt.datetime.now(dt.timezone.utc)
    # 首次提问时自动更新标题
    msg_count = chat_repository.get_message_count(db, body.session_id)
    if msg_count <= 2 and body.question.strip():
        title = body.question.strip()[:24]
        title = title.replace("\n", " ")
        if len(body.question.strip()) > 24:
            title += "..."
        session.title = title
    db.flush()

    # 获取性能细分（从 RAGService 内部计时）
    rag_raw = getattr(adapter, '_last_raw_result', None)
    emb_s = rag_raw.get("embedding_seconds", 0) if rag_raw else 0
    ret_s = rag_raw.get("retrieval_seconds", 0) if rag_raw else 0
    llm_s = rag_raw.get("llm_seconds", 0) if rag_raw else 0

    logger.info(
        "send_message | user=%s | session_id=%d | question_len=%d | "
        "refused=%s | total=%.3fs | RAG: embedding %.1fs retrieval %.1fs LLM %.1fs | request_id=%s",
        current_user.username,
        body.session_id,
        len(body.question),
        result.refused,
        latency,
        emb_s,
        ret_s,
        llm_s,
        request_id,
    )

    return SendMessageResponse(
        success=True,
        answer=result.answer,
        refused=result.refused,
        refusal_reason=result.refusal_reason,
        model_name=result.model,
        latency_seconds=latency,
        request_id=request_id,
        user_message=MessageResponse(
            id=user_msg.id,
            session_id=user_msg.session_id,
            role=user_msg.role,
            content=user_msg.content,
            created_at=user_msg.created_at,
        ),
        assistant_message=MessageResponse(
            id=assistant_msg.id,
            session_id=assistant_msg.session_id,
            role=assistant_msg.role,
            content=assistant_msg.content,
            created_at=assistant_msg.created_at,
        ),
    )


@router.delete("/chat/sessions/{session_id}", response_model=DeleteSessionResponse)
async def delete_session_handler(
    session_id: int,
    current_user: User = Depends(require_normal_user),
    db: Session = Depends(get_db),
):
    """删除指定会话及其所有消息。

    只能删除自己的会话，级联删除所有消息。
    """
    deleted = chat_repository.delete_session(db, session_id, current_user.id)

    if not deleted:
        raise HTTPException(
            status_code=404,
            detail="会话不存在或无权访问",
        )

    logger.info(
        "delete_session | user=%s | session_id=%d",
        current_user.username,
        session_id,
    )

    return DeleteSessionResponse(
        success=True,
        message="会话已删除",
        session_id=session_id,
    )


@router.put("/chat/sessions/{session_id}/title", response_model=UpdateSessionTitleResponse)
async def update_session_title_handler(
    session_id: int,
    body: UpdateSessionTitleRequest,
    current_user: User = Depends(require_normal_user),
    db: Session = Depends(get_db),
):
    """更新会话标题。

    只能修改自己的会话标题。
    """
    session = chat_repository.update_session_title(
        db, session_id, current_user.id, body.title
    )

    if session is None:
        raise HTTPException(
            status_code=404,
            detail="会话不存在或无权访问",
        )

    logger.info(
        "update_session_title | user=%s | session_id=%d | title=%s",
        current_user.username,
        session_id,
        body.title,
    )

    return UpdateSessionTitleResponse(
        success=True,
        message="会话标题已更新",
        session_id=session_id,
        title=session.title,
    )


@router.delete("/chat/sessions/{session_id}/messages", response_model=ClearSessionResponse)
async def clear_session_messages_handler(
    session_id: int,
    current_user: User = Depends(require_normal_user),
    db: Session = Depends(get_db),
):
    """清空指定会话的所有消息。

    只能清空自己的会话消息，会话本身保留。
    """
    deleted_count = chat_repository.clear_session_messages_for_user(
        db, session_id, current_user.id
    )

    if deleted_count is None:
        raise HTTPException(
            status_code=404,
            detail="会话不存在或无权访问",
        )

    logger.info(
        "clear_session_messages | user=%s | session_id=%d | deleted=%d",
        current_user.username,
        session_id,
        deleted_count,
    )

    return ClearSessionResponse(
        success=True,
        message=f"已清空 {deleted_count} 条消息",
        session_id=session_id,
        deleted_count=deleted_count,
    )


@router.delete("/chat/messages/{message_id}", response_model=DeleteMessageResponse)
async def delete_message_handler(
    message_id: int,
    current_user: User = Depends(require_normal_user),
    db: Session = Depends(get_db),
):
    """删除指定消息。

    只能删除自己会话中的消息（通过 JOIN 验证会话所有权）。
    """
    deleted = chat_repository.delete_message_for_user(
        db, message_id, current_user.id
    )

    if not deleted:
        raise HTTPException(
            status_code=404,
            detail="消息不存在或无权访问",
        )

    logger.info(
        "delete_message | user=%s | message_id=%d",
        current_user.username,
        message_id,
    )

    return DeleteMessageResponse(
        success=True,
        message="消息已删除",
        message_id=message_id,
    )


@router.post("/chat/messages/{message_id}/feedback", response_model=MessageFeedbackResponse)
async def submit_message_feedback(
    message_id: int,
    body: MessageFeedbackRequest,
    current_user: User = Depends(require_normal_user),
    db: Session = Depends(get_db),
):
    """提交消息反馈（点赞/点踩）。

    只能对自己会话中的消息提交反馈。
    反馈记录保存在消息记录中（通过 content 扩展存储）。
    """
    message = chat_repository.get_message_by_id_for_user(
        db, message_id, current_user.id
    )

    if message is None:
        raise HTTPException(
            status_code=404,
            detail="消息不存在或无权访问",
        )

    # 将反馈信息追加到消息内容末尾（作为元数据标记）
    # 实际产品中可以创建独立的 feedback 表，这里保持简单
    feedback_tag = f"\n<!-- feedback: rating={body.rating}"
    if body.comment:
        feedback_tag += f", comment={body.comment}"
    feedback_tag += " -->"

    # 移除旧反馈标记（如果存在）
    import re
    cleaned = re.sub(r"\n<!-- feedback:.*?-->", "", message.content)
    message.content = cleaned + feedback_tag
    db.flush()

    logger.info(
        "message_feedback | user=%s | message_id=%d | rating=%s",
        current_user.username,
        message_id,
        body.rating,
    )

    return MessageFeedbackResponse(
        success=True,
        message="反馈已提交",
        message_id=message_id,
        rating=body.rating,
    )


# ============================================================================
# 内部辅助
# ============================================================================


def _build_debug_response(debug_raw: dict) -> DebugInfo:
    """将 RAG 原始调试数据转换为 API 响应格式 — RAG 3.0 增强版。

    Parameters
    ----------
    debug_raw : dict
        RAGService.ask() 返回的 debug_info

    Returns
    -------
    DebugInfo
    """
    # 初始检索结果（含 score 详情）
    initial = [
        DebugResultItem(
            rank=r.get("rank", i + 1),
            file_name=r.get("file_name", "未知"),
            chunk_id=r.get("chunk_id", ""),
            content_preview=r.get("content_preview", ""),
            hybrid_score=r.get("hybrid_score"),
            vector_score=r.get("vector_score"),
            bm25_score=r.get("bm25_score"),
        )
        for i, r in enumerate(debug_raw.get("initial_results", []))
    ]

    # Reranked 结果
    reranked_raw = debug_raw.get("reranked_results")
    reranked = None
    if reranked_raw:
        reranked = [
            DebugResultItem(
                rank=r.get("rank", i + 1),
                file_name=r.get("file_name", "未知"),
                chunk_id=r.get("chunk_id", ""),
                content_preview=r.get("content_preview", ""),
                rerank_score=r.get("rerank_score"),
            )
            for i, r in enumerate(reranked_raw)
        ]

    # 最终结果
    final = [
        DebugResultItem(
            rank=r.get("rank", i + 1),
            file_name=r.get("file_name", "未知"),
            chunk_id=r.get("chunk_id", ""),
            content_preview=r.get("content_preview", ""),
            version=r.get("version"),
            page=r.get("page"),
        )
        for i, r in enumerate(debug_raw.get("final_results", []))
    ]

    # 配置
    config_raw = debug_raw.get("config")
    config = None
    if config_raw:
        config = DebugConfig(
            vector_weight=config_raw.get("vector_weight", 0.7),
            keyword_weight=config_raw.get("keyword_weight", 0.3),
            rerank_enabled=config_raw.get("rerank_enabled", True),
            fetch_k=config_raw.get("fetch_k", 20),
            rerank_top_k=config_raw.get("rerank_top_k", 5),
            max_raw_distance=config_raw.get("max_raw_distance", 1.15),
            min_relevance_score=config_raw.get("min_relevance_score", 0.32),
        )

    # 检索统计 (Phase 3: RAG 日志增强)
    stats_raw = debug_raw.get("retrieval_stats", {})
    retrieval_stats = None
    if stats_raw:
        retrieval_stats = {
            "vector_recall_count": stats_raw.get("vector_recall_count", 0),
            "bm25_recall_count": stats_raw.get("bm25_recall_count", 0),
            "fusion_total": stats_raw.get("fusion_total", 0),
            "reranker_input_count": stats_raw.get("reranker_input_count", 0),
            "reranker_output_count": stats_raw.get("reranker_output_count", 0),
            "final_context_count": stats_raw.get("final_context_count", 0),
        }

    return DebugInfo(
        query=debug_raw.get("query", ""),
        query_rewrite=debug_raw.get("query_rewrite"),
        retrieval_stats=retrieval_stats,
        initial_results=initial,
        reranked_results=reranked,
        final_results=final,
        refused=debug_raw.get("refused", False),
        refusal_reason=debug_raw.get("refusal_reason"),
        config=config,
    )
