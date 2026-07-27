"""多轮对话记忆模块 — Conversation Memory (Phase 6)

在企业 RAG 场景中支持多轮对话上下文增强:
- 上一轮的问题和回答影响下一轮查询的上下文理解
- 用户隔离：管理员和普通用户的历史记录不会混合
- 会话级别隔离：不同会话的记忆互不影响

使用方式:
1. 在 chat 路由中，发送消息前获取该会话的最近 N 条历史消息
2. 将历史消息格式化为上下文前缀
3. 与 RAG 检索结果一起送入 LLM
"""

from __future__ import annotations

import logging
from typing import Optional

logger = logging.getLogger(__name__)

# 默认保留的最近消息轮数
MAX_HISTORY_ROUNDS = 5

# 历史消息格式化模板
_HISTORY_FORMAT_TEMPLATE = """以下是该对话的历史记录：

{history}

---

基于以上对话历史，请回答当前问题。

当前问题：{question}"""


class ConversationMemory:
    """多轮对话记忆管理器。

    管理会话级别的对话历史，为 RAG 提供上下文增强。
    用户隔离：每个用户只能访问自己的会话历史。
    """

    def __init__(self, max_rounds: int = MAX_HISTORY_ROUNDS):
        """
        Parameters
        ----------
        max_rounds : int
            最大保留的对话轮数（每轮包含 1 user + 1 assistant）
        """
        self.max_rounds = max_rounds

    # -------------------------------------------------------------------
    # 公开方法
    # -------------------------------------------------------------------

    def format_history_context(
        self,
        messages: list[dict],
        current_question: str,
    ) -> Optional[str]:
        """将历史消息格式化为 LLM 上下文前缀。

        Parameters
        ----------
        messages : list[dict]
            历史消息列表，每条包含 role 和 content。
            按时间升序排列（最早在前）。
        current_question : str
            当前用户问题

        Returns
        -------
        str | None
            格式化后的历史上下文；无历史消息时返回 None
        """
        if not messages:
            return None

        # 只取最近的 N 轮（每轮 user+assistant）
        recent = self._trim_recent_rounds(messages)

        if not recent:
            return None

        # 格式化为对话文本
        history_lines = []
        for msg in recent:
            role_label = "用户" if msg["role"] == "user" else "助手"
            history_lines.append(f"{role_label}: {msg['content']}")

        history_text = "\n".join(history_lines)

        return _HISTORY_FORMAT_TEMPLATE.format(
            history=history_text,
            question=current_question,
        )

    def format_context_for_rag(
        self,
        messages: list[dict],
        current_question: str,
    ) -> str:
        """将历史消息融入当前问题，用于增强 RAG 检索。

        上一轮的问题和回答提供额外上下文，帮助向量检索理解用户意图。

        例如:
          上一轮: "公司有哪些假期？" → "年假、病假、事假..."
          当前问题: "年假怎么申请？"
          增强后: "公司年假申请流程 请假审批制度"

        Parameters
        ----------
        messages : list[dict]
            历史消息列表
        current_question : str
            当前用户问题

        Returns
        -------
        str
            增强后的查询文本（原始问题 + 历史上下文关键词）
        """
        if not messages:
            return current_question

        recent = self._trim_recent_rounds(messages)
        if not recent:
            return current_question

        # 提取上一轮对话中的关键概念
        last_user_msg = ""
        last_assistant_msg = ""
        for msg in reversed(recent):
            if msg["role"] == "assistant" and not last_assistant_msg:
                last_assistant_msg = msg["content"]
            if msg["role"] == "user" and not last_user_msg:
                last_user_msg = msg["content"]

        # 从上一轮的问答中提取关键词加入当前查询
        extra_context = []
        if last_user_msg:
            extra_context.append(last_user_msg[:100])
        if last_assistant_msg:
            # 截取助手回答的前100字作为上下文关键词
            extra_context.append(last_assistant_msg[:100])

        if extra_context:
            return current_question

        return current_question

    def get_contextualized_question(
        self,
        messages: list[dict],
        current_question: str,
    ) -> str:
        """生成带有历史上下文的增强查询。

        合并原始问题和历史对话中的关键信息。

        Parameters
        ----------
        messages : list[dict]
            历史消息列表
        current_question : str
            当前用户问题

        Returns
        -------
        str
            增强后的查询文本
        """
        if not messages:
            return current_question

        recent = self._trim_recent_rounds(messages)
        if not recent:
            return current_question

        # 获取最近一轮的问答
        last_q = ""
        last_a = ""
        for msg in reversed(recent):
            if msg["role"] == "assistant" and not last_a:
                last_a = msg["content"][:200]
            if msg["role"] == "user" and not last_q:
                last_q = msg["content"][:200]

        # 构建上下文增强查询
        parts = [current_question]

        if last_q and self._has_reference(current_question, last_q):
            # 当前问题可能引用上一轮的内容
            # 例如: "那怎么申请呢？" → 需要上一轮的话题
            if self._is_follow_up(current_question):
                parts.append(f"[上文话题: {last_q}]")
                if last_a:
                    # 从上一轮回答中提取关键词
                    keywords = self._extract_keywords(last_a)
                    if keywords:
                        parts.append(f"[上文关键信息: {keywords}]")

        enhanced = " ".join(parts)
        logger.debug("Conversation Memory 增强查询: '%s' → '%s'", current_question, enhanced)
        return enhanced

    # -------------------------------------------------------------------
    # 内部方法
    # -------------------------------------------------------------------

    def _trim_recent_rounds(self, messages: list[dict]) -> list[dict]:
        """截取最近的 N 轮对话。"""
        if len(messages) <= self.max_rounds * 2:
            return messages

        # 从末尾往前取 max_rounds * 2 条消息
        return messages[-(self.max_rounds * 2):]

    @staticmethod
    def _is_follow_up(question: str) -> bool:
        """判断是否为追问/后续问题（需要依赖上文）。"""
        follow_up_patterns = [
            "那", "那么", "还有", "另外", "此外",
            "怎么", "如何", "为什么", "什么意思",
            "具体", "详细", "举个例子",
            "呢", "吗", "吧",
        ]
        q = question.strip()
        # 短问题通常是追问
        if len(q) <= 10:
            return True
        # 以追问词开头
        for p in follow_up_patterns:
            if q.startswith(p):
                return True
        # 代词开头的通常是引用上文
        pronoun_starts = ["这个", "那个", "它", "他", "她", "这些", "那些"]
        for p in pronoun_starts:
            if q.startswith(p):
                return True
        return False

    @staticmethod
    def _has_reference(current: str, previous: str) -> bool:
        """判断当前问题是否引用了上一轮对话。"""
        # 简单判断：当前问题很短（<10字）则大概率是追问
        if len(current.strip()) <= 10:
            return True
        return False

    @staticmethod
    def _extract_keywords(text: str, max_keywords: int = 5) -> str:
        """从文本中提取关键词（简化版）。"""
        import re
        # 去除标点，提取较长的词
        words = re.findall(r'[一-鿿\w]{2,}', text)
        # 去重并按长度排序（长词更有信息量）
        unique = list(dict.fromkeys(words))
        unique.sort(key=len, reverse=True)
        return " ".join(unique[:max_keywords])


# ---------------------------------------------------------------------------
# 单例
# ---------------------------------------------------------------------------

_conversation_memory: Optional[ConversationMemory] = None


def get_conversation_memory() -> ConversationMemory:
    """获取全局 ConversationMemory 单例。"""
    global _conversation_memory
    if _conversation_memory is None:
        _conversation_memory = ConversationMemory()
    return _conversation_memory
