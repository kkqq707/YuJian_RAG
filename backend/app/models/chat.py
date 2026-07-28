"""聊天会话数据模型

- ChatSession: 聊天会话（属于一个用户）
- ChatMessage: 会话中的单条消息
- 级联删除: 删除会话时自动删除所有消息
- 用户隔离: 通过 user_id 外键关联用户
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship

from backend.app.models.base import Base


class ChatSession(Base):
    """聊天会话。

    每个会话属于一个用户，包含多条消息。
    """

    __tablename__ = "chat_sessions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    title = Column(String(255), nullable=False, default="新对话")
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    # 关系
    user = relationship("User", backref="chat_sessions")
    messages = relationship(
        "ChatMessage",
        back_populates="session",
        cascade="all, delete-orphan",
        order_by="ChatMessage.created_at",
    )

    def __repr__(self) -> str:
        return (
            f"ChatSession(id={self.id}, user_id={self.user_id}, "
            f"title={self.title!r})"
        )


class ChatMessage(Base):
    """聊天消息。

    每条消息属于一个会话，role 为 'user' 或 'assistant'。
    """

    __tablename__ = "chat_messages"

    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(
        Integer,
        ForeignKey("chat_sessions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    role = Column(String(20), nullable=False, default="user")
    content = Column(Text, nullable=False, default="")
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
    is_test = Column(
        Boolean,
        nullable=False,
        default=False,
        server_default="0",
        comment="是否为测试消息（管理员调试模式），工作台统计排除此类消息",
    )

    # 关系
    session = relationship("ChatSession", back_populates="messages")

    def __repr__(self) -> str:
        content_preview = (
            self.content[:50] + "..." if len(self.content) > 50 else self.content
        )
        return (
            f"ChatMessage(id={self.id}, session_id={self.session_id}, "
            f"role={self.role!r}, content={content_preview!r})"
        )
