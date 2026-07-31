"""游客聊天服务 — 无认证、无用户关联的公开问答

- 复用 RAGAdapter.ask_user() 进行 RAG 问答
- 不创建用户、不保存聊天记录
- 不访问用户数据库
- 返回与普通用户聊天相同格式的答案（不含来源）
"""

from __future__ import annotations

import logging
import time
import uuid

from backend.app.config import get_settings
from backend.app.services.rag_adapter import get_rag_adapter, UserChatResult

logger = logging.getLogger(__name__)


class PublicChatService:
    """游客聊天服务。

    职责:
    - 调用 RAGAdapter.ask_user() 获取回答
    - 不创建用户、不保存聊天记录
    - 通过 Host 白名单控制访问来源
    """

    def __init__(self):
        self._adapter = None

    @property
    def adapter(self):
        if self._adapter is None:
            self._adapter = get_rag_adapter()
        return self._adapter

    @staticmethod
    def is_host_allowed(host: str | None) -> bool:
        """检查请求来源 Host 是否在允许列表中。

        未配置 PUBLIC_CHAT_ALLOWED_HOSTS 时默认拒绝所有外部请求。
        设置 "*" 允许所有来源（仅开发环境推荐）。

        Parameters
        ----------
        host : str | None
            请求头中的 Host 值

        Returns
        -------
        bool
        """
        settings = get_settings()
        allowed = settings.PUBLIC_CHAT_ALLOWED_HOSTS

        if not allowed:
            logger.warning("PUBLIC_CHAT_ALLOWED_HOSTS 未配置，拒绝游客聊天请求")
            return False

        if "*" in allowed:
            return True

        if not host:
            return False

        # 去除端口号比较
        host_clean = host.split(":")[0].strip().lower()
        for entry in allowed:
            entry_clean = entry.strip().lower()
            if host_clean == entry_clean:
                return True

        return False

    def ask(self, question: str) -> UserChatResult:
        """游客问答 — 复用 RAGAdapter.ask_user()。

        Parameters
        ----------
        question : str
            用户问题

        Returns
        -------
        UserChatResult
        """
        t0 = time.perf_counter()
        request_id = str(uuid.uuid4())

        adapter = self.adapter
        result = adapter.ask_user(question)

        # 用实际耗时覆盖 adapter 返回的 latency
        latency = round(time.perf_counter() - t0, 3)
        result.latency_seconds = latency
        result.request_id = request_id

        logger.info(
            "public_chat | question_len=%d | refused=%s | latency=%.3fs | request_id=%s",
            len(question),
            result.refused,
            latency,
            request_id,
        )

        return result


# ---------------------------------------------------------------------------
# 单例
# ---------------------------------------------------------------------------

from functools import lru_cache


@lru_cache(maxsize=1)
def get_public_chat_service() -> PublicChatService:
    """获取缓存的 PublicChatService 单例。"""
    return PublicChatService()
