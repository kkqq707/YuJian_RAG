"""SQLite 锁错误识别与有限重试工具

Phase 7: 对可安全重试的短写操作进行有限次数重试。

重试策略：
- 指数退避: 100ms, 200ms, 400ms (默认配置)
- 加入随机抖动
- 每次重试前 rollback + 使用干净 Session
- 不复用失败状态的 Session

只重试满足条件的异常：
- SQLAlchemy OperationalError
- 底层错误明确包含 "database is locked" 或 "database table is locked"

不重试：
- IntegrityError（唯一约束冲突、外键错误等）
- 权限错误
- 参数错误
- 业务校验失败
- 所有未知异常
"""

from __future__ import annotations

import asyncio
import functools
import logging
import random
import time
import uuid
from typing import Any, Callable, TypeVar

from sqlalchemy.exc import IntegrityError, OperationalError
from sqlalchemy.orm import Session

from backend.app.config import get_settings
from backend.app.database import SessionLocal

logger = logging.getLogger(__name__)

F = TypeVar("F", bound=Callable[..., Any])

# 需要重试的 SQLite 错误关键词
_RETRYABLE_KEYWORDS = (
    "database is locked",
    "database table is locked",
)

# 不应重试的错误关键词（明确排除）
_NON_RETRYABLE_KEYWORDS = (
    "no such table",
    "no such column",
    "syntax error",
    "readonly",
    "read-only",
    "disk i/o error",
    "malformed",
    "corrupt",
)


def _is_retryable_locked_error(exc: OperationalError) -> bool:
    """判断 OperationalError 是否来自 SQLite 锁错误。

    只匹配包含 "database is locked" 或 "database table is locked" 的错误。
    排除其他明确不可重试的 SQLite 错误。
    """
    msg = str(exc).lower()
    msg_orig = str(exc.orig).lower() if exc.orig else ""

    combined = f"{msg} {msg_orig}"

    # 先检查非重试关键词
    for kw in _NON_RETRYABLE_KEYWORDS:
        if kw in combined:
            return False

    # 检查重试关键词
    for kw in _RETRYABLE_KEYWORDS:
        if kw.lower() in combined:
            return True

    return False


def execute_with_db_retry_sync(
    operation: Callable[[Session], Any],
    session_factory: Callable[[], Session] | None = None,
    request_id: str = "",
    operation_name: str = "",
) -> Any:
    """同步执行数据库操作，遇锁时重试。

    Parameters
    ----------
    operation : Callable[[Session], Any]
        接收 Session 参数的可调用对象，返回业务结果
    session_factory : Callable[[], Session], optional
        Session 工厂函数。默认使用 SessionLocal
    request_id : str
        请求 ID（用于日志）
    operation_name : str
        操作名称（用于日志）

    Returns
    -------
    Any
        operation 的返回值

    Raises
    ------
    DatabaseBusyError
        重试耗尽后的锁错误
    IntegrityError
        不重试的约束冲突
    Exception
        其他不重试的异常

    注意事项：
    - 每次重试创建新的 Session
    - 失败 Session 自动 rollback + close
    - 成功提交由调用方负责（operation 内部）或返回后提交
    """
    settings = get_settings()
    max_retries = settings.SQLITE_LOCK_RETRY_COUNT
    base_delay_ms = settings.SQLITE_LOCK_RETRY_BASE_DELAY_MS
    base_delay_s = base_delay_ms / 1000.0

    factory = session_factory or SessionLocal
    last_error: Exception | None = None
    request_id = request_id or str(uuid.uuid4())

    for attempt in range(max_retries + 1):  # 0..retry_count，第 0 次是初始尝试
        db: Session | None = None
        try:
            db = factory()
            result = operation(db)
            return result
        except IntegrityError:
            # 约束冲突不重试，直接抛出
            if db:
                try:
                    db.rollback()
                except Exception:
                    pass
            raise
        except OperationalError as e:
            if db:
                try:
                    db.rollback()
                except Exception:
                    pass

            if not _is_retryable_locked_error(e):
                # 非锁相关的 OperationalError 不重试
                raise

            last_error = e

            if attempt < max_retries:
                # 指数退避 + 随机抖动
                delay_s = base_delay_s * (2 ** attempt)
                jitter = random.uniform(0, delay_s * 0.3)
                delay_ms = (delay_s + jitter) * 1000

                logger.warning(
                    "db_retry | request_id=%s operation=%s attempt=%d/%d delay_ms=%.0f",
                    request_id, operation_name, attempt + 1, max_retries, delay_ms,
                )
                time.sleep(delay_s + jitter)
            else:
                logger.error(
                    "db_retry_exhausted | request_id=%s operation=%s attempts=%d",
                    request_id, operation_name, max_retries + 1,
                )
                raise DatabaseBusyError() from e
        except Exception:
            if db:
                try:
                    db.rollback()
                except Exception:
                    pass
            raise
        finally:
            if db and attempt > 0 and last_error is not None:
                # 在重试路径上，失败 Session 已经 rollback，需要 close
                try:
                    db.close()
                except Exception:
                    pass

    # 理论上不会到达这里
    raise DatabaseBusyError()


async def execute_with_db_retry_async(
    operation: Callable[[Session], Any],
    session_factory: Callable[[], Session] | None = None,
    request_id: str = "",
    operation_name: str = "",
) -> Any:
    """异步包装 — 在 executor 中执行同步重试逻辑，避免阻塞事件循环。

    适用于 FastAPI 异步路由中需要重试的短数据库写操作。
    """
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(
        None,
        functools.partial(
            execute_with_db_retry_sync,
            operation=operation,
            session_factory=session_factory,
            request_id=request_id,
            operation_name=operation_name,
        ),
    )


# ---------------------------------------------------------------------------
# 便捷装饰器
# ---------------------------------------------------------------------------


def db_retry(request_id: str = "", operation_name: str = ""):
    """同步函数装饰器 — 遇 SQLite 锁时重试。

    用法：
        @db_retry(request_id="...", operation_name="save_message")
        def save_data(db: Session):
            ...

    注意：被装饰函数必须接受 Session 作为第一个参数。
    """
    def decorator(func: F) -> F:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            # 提取 request_id 参数（如果存在）
            rid = request_id
            op_name = operation_name or func.__name__
            return execute_with_db_retry_sync(
                lambda db: func(db, *args[1:], **kwargs),
                request_id=rid,
                operation_name=op_name,
            )
        return wrapper  # type: ignore[return-value]
    return decorator


# ---------------------------------------------------------------------------
# 异常
# ---------------------------------------------------------------------------


class DatabaseBusyError(Exception):
    """数据库繁忙异常 — 重试耗尽后抛出。

    对应 HTTP 503 + DATABASE_BUSY 错误码。
    """

    def __init__(self, message: str = "数据库当前繁忙，请稍后重试"):
        self.message = message
        super().__init__(message)
