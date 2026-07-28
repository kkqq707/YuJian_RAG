"""测试配置 — 提供测试 fixtures：数据库、测试用户、认证 Token"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Generator

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

# 确保项目根在路径中
project_root = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / "backend"))

from backend.app.models.base import Base
from backend.app.models.user import User


# ---------------------------------------------------------------------------
# 测试应用（无 lifespan）
# ---------------------------------------------------------------------------

def _create_test_app() -> FastAPI:
    """创建测试 FastAPI 应用（无 lifespan，不加载模型）。"""
    from backend.app.config import get_settings
    from fastapi.middleware.cors import CORSMiddleware

    settings = get_settings()

    app = FastAPI(
        title=settings.APP_NAME + " Test",
        version=settings.APP_VERSION,
        docs_url=None,
        redoc_url=None,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    from backend.app.api.router import api_router
    app.include_router(api_router)

    from backend.app.exceptions import register_exception_handlers
    register_exception_handlers(app)

    return app


# ---------------------------------------------------------------------------
# 内存数据库（每次测试独立）
# ---------------------------------------------------------------------------

@pytest.fixture(scope="function")
def db_session() -> Generator[Session, None, None]:
    """函数级独立内存 SQLite 数据库。"""
    engine = create_engine(
        "sqlite:///:memory:",
        echo=False,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    @event.listens_for(engine, "connect")
    def _set_pragma(dbapi_connection, _record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    Base.metadata.create_all(bind=engine)

    TestSession = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    session = TestSession()
    try:
        yield session
    finally:
        session.rollback()
        session.close()
        Base.metadata.drop_all(bind=engine)
        engine.dispose()


# ---------------------------------------------------------------------------
# FastAPI TestClient（函数级，覆盖 get_db 依赖）
# ---------------------------------------------------------------------------

@pytest.fixture(scope="function")
def client(db_session: Session) -> Generator[TestClient, None, None]:
    """创建 FastAPI TestClient，覆盖 get_db 依赖使用测试数据库。"""
    from backend.app.database import get_db

    app = _create_test_app()

    # 使用闭包捕获 db_session，确保每次 API 调用使用相同的 session
    def _override_get_db():
        try:
            yield db_session
            db_session.commit()
        except Exception:
            db_session.rollback()
            raise

    app.dependency_overrides[get_db] = _override_get_db

    with TestClient(app, base_url="http://test") as c:
        yield c

    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# 测试用户（函数级）
# ---------------------------------------------------------------------------

def _create_test_user(db: Session, username: str, role: str = "user", password: str = "test123456") -> User:
    """创建测试用户（若已存在则返回已有用户）。"""
    from sqlalchemy import select as sa_select
    stmt = sa_select(User).where(User.username == username)
    existing = db.execute(stmt).scalar_one_or_none()
    if existing:
        return existing

    import bcrypt
    password_hash = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")
    user = User(
        username=username,
        display_name=username.capitalize(),
        email=f"{username}@test.com",
        password_hash=password_hash,
        role=role,
        is_active=True,
        is_superuser=(role == "admin"),
    )
    db.add(user)
    db.flush()
    db.refresh(user)
    # commit 后用户对同一 session 可见（已 flush）；对其他 session 可见（已 commit）
    db.commit()
    return user


def _get_auth_headers(user: User) -> dict:
    """为测试用户生成认证头。"""
    from backend.app.security.jwt import create_access_token
    token = create_access_token(user)
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture(scope="function")
def user_a(db_session: Session) -> User:
    return _create_test_user(db_session, "user_a_test", role="user")


@pytest.fixture(scope="function")
def user_b(db_session: Session) -> User:
    return _create_test_user(db_session, "user_b_test", role="user")


@pytest.fixture(scope="function")
def admin(db_session: Session) -> User:
    return _create_test_user(db_session, "admin_test_user", role="admin")


@pytest.fixture(scope="function")
def user_a_headers(user_a: User) -> dict:
    return _get_auth_headers(user_a)


@pytest.fixture(scope="function")
def user_b_headers(user_b: User) -> dict:
    return _get_auth_headers(user_b)


@pytest.fixture(scope="function")
def admin_headers(admin: User) -> dict:
    return _get_auth_headers(admin)
