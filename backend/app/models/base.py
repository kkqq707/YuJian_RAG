"""SQLAlchemy 声明式基类"""

from __future__ import annotations

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """声明式基类 — 所有 ORM 模型继承此类。"""
    pass
