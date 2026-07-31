"""游客聊天路由 — 无需认证即可访问的公开问答

- POST /api/v1/public/chat: 公开聊天
- 无 JWT 验证
- 无 user_id 关联
- 不创建用户、不保存消息
- Host 白名单控制访问来源
- IP 限流保护

安全策略:
1. 必须通过 Host 白名单校验（PUBLIC_CHAT_ALLOWED_HOSTS）
2. IP 级别限流（public_chat 规则）
3. 问题长度限制与普通用户一致
4. 不返回来源/调试信息
"""

from __future__ import annotations

import logging
import time
import uuid

from fastapi import APIRouter, Depends, HTTPException, Request

from backend.app.client_ip import get_client_ip
from backend.app.config import get_settings
from backend.app.rate_limiter import check_rate_limit
from backend.app.schemas.chat import ChatRequest, UserChatResponse
from backend.app.services.public_chat_service import (
    PublicChatService,
    get_public_chat_service,
)

logger = logging.getLogger(__name__)

router = APIRouter(tags=["游客聊天"])


@router.post("/public/chat", response_model=UserChatResponse)
async def public_chat(
    request: Request,
    body: ChatRequest,
):
    """游客问答 — 无需登录，通过 Host 白名单 + IP 限流保护。

    与普通用户聊天使用相同的 RAGAdapter.ask_user()，
    返回相同的 UserChatResponse 格式（不含来源）。
    不创建用户、不保存消息、不访问用户数据库。

    访问控制:
    - Host 头必须在 PUBLIC_CHAT_ALLOWED_HOSTS 白名单中
    - IP 级别限流（独立于已认证用户的限流额度）
    """
    request_id = getattr(request.state, "request_id", str(uuid.uuid4()))

    # ---- 1. Host 白名单校验 ----
    host = request.headers.get("host", "")
    if not PublicChatService.is_host_allowed(host):
        logger.warning(
            "public_chat 拒绝 | host=%s | request_id=%s",
            host or "(missing)",
            request_id,
        )
        raise HTTPException(
            status_code=403,
            detail="该服务需要从授权的域名访问，请联系管理员",
        )

    # ---- 2. IP 限流 ----
    client_ip, _ = get_client_ip(request)
    check_rate_limit(client_ip, "public_chat")

    # ---- 3. 问题长度校验（与 ChatRequest 中的 max_length 重复校验，安全兜底） ----
    settings = get_settings()
    question = body.question.strip()
    if len(question) > settings.MAX_QUESTION_LENGTH:
        raise HTTPException(
            status_code=422,
            detail=f"问题长度不能超过 {settings.MAX_QUESTION_LENGTH} 个字符",
        )

    # ---- 4. 调用 RAG ----
    t0 = time.perf_counter()
    service = get_public_chat_service()
    result = service.ask(question)

    logger.info(
        "public_chat | ip=%s | question_len=%d | refused=%s | latency=%.3fs | request_id=%s",
        client_ip,
        len(question),
        result.refused,
        result.latency_seconds,
        request_id,
    )

    return UserChatResponse(
        success=True,
        answer=result.answer,
        refused=result.refused,
        refusal_reason=result.refusal_reason,
        model_name=result.model,
        latency_seconds=result.latency_seconds,
        request_id=request_id,
    )
