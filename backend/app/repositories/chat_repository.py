"""聊天会话 & 消息数据库访问层

- 所有查询限定 user_id，实现用户隔离
- 删除会话级联删除消息（ORM 关系已配置 cascade）
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import desc
from sqlalchemy.orm import Session, joinedload

from backend.app.models.chat import ChatSession, ChatMessage

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# 会话
# ---------------------------------------------------------------------------


def get_user_sessions(
    db: Session, user_id: int, page: int = 1, page_size: int = 20
) -> list[ChatSession]:
    """获取用户的会话列表，按更新时间降序排列（分页）。

    Parameters
    ----------
    db : Session
    user_id : int
    page : int
        页码（从 1 开始）
    page_size : int
        每页数量

    Returns
    -------
    list[ChatSession]
    """
    offset = (page - 1) * page_size
    return (
        db.query(ChatSession)
        .filter(ChatSession.user_id == user_id)
        .order_by(desc(ChatSession.updated_at))
        .offset(offset)
        .limit(page_size)
        .all()
    )


def get_user_sessions_count(db: Session, user_id: int) -> int:
    """获取用户会话总数。

    Parameters
    ----------
    db : Session
    user_id : int

    Returns
    -------
    int
    """
    return (
        db.query(ChatSession)
        .filter(ChatSession.user_id == user_id)
        .count()
    )


def get_session_by_id(
    db: Session, session_id: int, user_id: int
) -> Optional[ChatSession]:
    """根据 ID 获取会话（同时验证所有权）。

    Parameters
    ----------
    db : Session
    session_id : int
    user_id : int

    Returns
    -------
    Optional[ChatSession]
    """
    return (
        db.query(ChatSession)
        .filter(
            ChatSession.id == session_id,
            ChatSession.user_id == user_id,
        )
        .first()
    )


def create_session(
    db: Session, user_id: int, title: str = "新对话"
) -> ChatSession:
    """创建新会话。

    Parameters
    ----------
    db : Session
    user_id : int
    title : str

    Returns
    -------
    ChatSession
    """
    now = datetime.now(timezone.utc)
    session = ChatSession(
        user_id=user_id,
        title=title,
        created_at=now,
        updated_at=now,
    )
    db.add(session)
    db.flush()
    return session


def update_session_title(
    db: Session, session_id: int, user_id: int, title: str
) -> Optional[ChatSession]:
    """更新会话标题。

    Parameters
    ----------
    db : Session
    session_id : int
    user_id : int
    title : str

    Returns
    -------
    Optional[ChatSession]
    """
    session = get_session_by_id(db, session_id, user_id)
    if session is None:
        return None
    session.title = title
    session.updated_at = datetime.now(timezone.utc)
    db.flush()
    return session


def delete_session(db: Session, session_id: int, user_id: int) -> bool:
    """删除会话（级联删除所有消息）。

    Parameters
    ----------
    db : Session
    session_id : int
    user_id : int

    Returns
    -------
    bool
        True 表示删除成功，False 表示会话不存在或无权限
    """
    session = get_session_by_id(db, session_id, user_id)
    if session is None:
        return False
    db.delete(session)
    db.flush()
    return True


# ---------------------------------------------------------------------------
# 消息
# ---------------------------------------------------------------------------


def get_session_messages(
    db: Session, session_id: int, user_id: int
) -> Optional[list[ChatMessage]]:
    """获取会话的所有消息（按创建时间升序）。

    先验证会话所有权，再返回消息。

    Parameters
    ----------
    db : Session
    session_id : int
    user_id : int

    Returns
    -------
    Optional[list[ChatMessage]]
        None 表示会话不存在或不属于该用户
    """
    session = get_session_by_id(db, session_id, user_id)
    if session is None:
        return None

    return (
        db.query(ChatMessage)
        .filter(ChatMessage.session_id == session_id)
        .order_by(ChatMessage.created_at)
        .all()
    )


def get_message_count(db: Session, session_id: int) -> int:
    """获取会话的消息数量（不验证所有权，仅用于已通过所有权验证的场景）。

    Parameters
    ----------
    db : Session
    session_id : int

    Returns
    -------
    int
    """
    return (
        db.query(ChatMessage)
        .filter(ChatMessage.session_id == session_id)
        .count()
    )


def get_message_count_for_user(
    db: Session, session_id: int, user_id: int
) -> Optional[int]:
    """获取会话的消息数量（同时验证所有权）。

    如果会话不属于当前用户，返回 None。

    Parameters
    ----------
    db : Session
    session_id : int
    user_id : int

    Returns
    -------
    Optional[int]
        None 表示会话不存在或不属于该用户
    """
    session = get_session_by_id(db, session_id, user_id)
    if session is None:
        return None
    return (
        db.query(ChatMessage)
        .filter(ChatMessage.session_id == session_id)
        .count()
    )


def get_message_by_id_for_user(
    db: Session, message_id: int, user_id: int
) -> Optional[ChatMessage]:
    """根据消息 ID 获取消息（同时验证会话所有权）。

    先通过 JOIN 验证消息所属会话属于当前用户，再返回消息。

    Parameters
    ----------
    db : Session
    message_id : int
    user_id : int

    Returns
    -------
    Optional[ChatMessage]
        None 表示消息不存在或会话不属于该用户
    """
    return (
        db.query(ChatMessage)
        .join(ChatSession, ChatMessage.session_id == ChatSession.id)
        .filter(
            ChatMessage.id == message_id,
            ChatSession.user_id == user_id,
        )
        .first()
    )


def create_message(
    db: Session, session_id: int, role: str, content: str,
    is_test: bool = False,
) -> ChatMessage:
    """创建消息（调用方必须先验证会话所有权）。

    Parameters
    ----------
    db : Session
    session_id : int
    role : str
        'user' 或 'assistant'
    content : str
    is_test : bool
        是否为测试消息（管理员调试模式），默认 False

    Returns
    -------
    ChatMessage
    """
    message = ChatMessage(
        session_id=session_id,
        role=role,
        content=content,
        is_test=is_test,
        created_at=datetime.now(timezone.utc),
    )
    db.add(message)
    db.flush()
    return message


def delete_message_for_user(
    db: Session, message_id: int, user_id: int
) -> bool:
    """删除消息（验证会话所有权）。

    Parameters
    ----------
    db : Session
    message_id : int
    user_id : int

    Returns
    -------
    bool
        True 表示删除成功，False 表示消息不存在或无权限
    """
    message = get_message_by_id_for_user(db, message_id, user_id)
    if message is None:
        return False
    db.delete(message)
    db.flush()
    return True


def clear_session_messages_for_user(
    db: Session, session_id: int, user_id: int
) -> Optional[int]:
    """清空会话的所有消息（验证会话所有权）。

    Parameters
    ----------
    db : Session
    session_id : int
    user_id : int

    Returns
    -------
    Optional[int]
        删除的消息数量，None 表示会话不存在或无权限
    """
    session = get_session_by_id(db, session_id, user_id)
    if session is None:
        return None

    count = (
        db.query(ChatMessage)
        .filter(ChatMessage.session_id == session_id)
        .count()
    )

    (
        db.query(ChatMessage)
        .filter(ChatMessage.session_id == session_id)
        .delete(synchronize_session="fetch")
    )

    # 更新会话时间
    session.updated_at = datetime.now(timezone.utc)
    db.flush()
    return count
