"""认证服务

提供:
- authenticate: 用户名密码认证
- issue_tokens: 签发 Token 对
- refresh_access_token: 刷新 Access Token（轮换策略）
- logout: 单设备退出
- logout_all: 全部设备退出
- change_password: 修改密码

安全要点:
- 用户不存在时执行等价密码哈希校验（减少用户枚举时序差异）
- 锁定提示不泄露用户是否存在
- Refresh Token 使用一次轮换策略
- 旧 Refresh Token 再次使用 → 撤销该用户相关 Token
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from backend.app.config import get_settings
from backend.app.models.user import User
from backend.app.repositories.token_repository import TokenRepository
from backend.app.repositories.user_repository import UserRepository
from backend.app.security.jwt import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_token,
    verify_access_token,
    verify_refresh_token,
)
from backend.app.security.password import (
    hash_password,
    validate_password_strength,
    verify_password,
)

logger = logging.getLogger(__name__)


class AuthService:
    """认证服务 — 管理登录、Token 和密码操作。"""

    def __init__(self, db: Session):
        self.db = db
        self.user_repo = UserRepository(db)
        self.token_repo = TokenRepository(db)
        self.settings = get_settings()

    # ------------------------------------------------------------------
    # 登录
    # ------------------------------------------------------------------

    def authenticate(
        self,
        username: str,
        password: str,
        ip: str | None = None,
        user_agent: str | None = None,
    ) -> dict:
        """用户名密码认证。

        登录流程:
        1. 查找用户
        2. 用户不存在时执行等价密码哈希（防用户枚举）
        3. 检查 is_active
        4. 检查 locked_until
        5. 验证密码
        6. 失败次数 +1，达到阈值锁定
        7. 成功后清零失败次数，更新 last_login_at
        8. 签发 Token

        Returns
        -------
        dict
            {"access_token": ..., "refresh_token": ..., "expires_in": ..., "user": ...}

        Raises
        ------
        AuthenticationError
            登录失败（统一提示，不区分用户不存在/密码错误）
        """
        logger.info("login attempt username=%s", username)

        user = self.user_repo.get_by_username(username)

        # 用户不存在 → 执行等价密码哈希，减少用户枚举时序差异
        if user is None:
            # 对假密码执行哈希，消耗相近时间
            try:
                verify_password(password, hash_password("dummy_placeholder_for_timing"))
            except Exception:
                pass  # 哈希失败不影响流程，已消耗计算时间
            logger.warning("login failed reason=user_not_found username=%s", username)
            raise AuthenticationError("用户名或密码错误")

        # 检查激活状态
        if not user.is_active:
            # 仍然执行密码哈希以掩盖用户存在
            try:
                verify_password(password, user.password_hash)
            except Exception:
                pass
            logger.warning("login failed reason=user_inactive username=%s", username)
            raise AuthenticationError("用户名或密码错误")

        # 检查锁定状态
        if user.is_locked:
            locked_str = user.locked_until.strftime("%Y-%m-%d %H:%M:%S UTC")
            logger.warning("login failed reason=account_locked username=%s", username)
            raise AuthenticationError(
                f"账户已被临时锁定，请于 {locked_str} 后重试"
            )

        # 验证密码
        try:
            password_ok = verify_password(password, user.password_hash)
        except Exception:
            # bcrypt 异常不暴露为 500，安全降级为密码错误
            password_ok = False

        if not password_ok:
            self.user_repo.record_login_failure(
                user,
                self.settings.MAX_LOGIN_ATTEMPTS,
                self.settings.LOGIN_LOCK_MINUTES,
            )
            remaining = self.settings.MAX_LOGIN_ATTEMPTS - user.failed_login_attempts
            logger.warning(
                "login failed reason=wrong_password username=%s remaining_attempts=%d",
                username,
                remaining,
            )
            raise AuthenticationError("用户名或密码错误")

        # 登录成功
        self.user_repo.record_login_success(user)
        logger.info(
            "login success username=%s role=%s user_id=%d",
            username,
            user.role,
            user.id,
        )
        return self.issue_tokens(user, ip, user_agent)

    # ------------------------------------------------------------------
    # Token 签发
    # ------------------------------------------------------------------

    def issue_tokens(
        self,
        user: User,
        ip: str | None = None,
        user_agent: str | None = None,
    ) -> dict:
        """为给定用户签发 Access + Refresh Token 对。"""
        access_token = create_access_token(user)
        refresh_token = create_refresh_token(user)

        # 解码 Refresh Token 获取 jti 和过期时间
        payload = decode_token(refresh_token)
        jti = payload["jti"]
        exp = datetime.fromtimestamp(payload["exp"], tz=timezone.utc)

        # 存储 Refresh Token 哈希
        self.token_repo.create(
            user_id=user.id,
            token_jti=jti,
            token_hash=hash_token(refresh_token),
            expires_at=exp,
            created_ip=ip,
            user_agent=user_agent,
        )

        # 检查是否首次登录（使用默认密码，password_changed_at 为 None）
        must_change = user.password_changed_at is None

        return {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_type": "bearer",
            "expires_in": self.settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
            "user": {
                "id": user.id,
                "username": user.username,
                "display_name": user.display_name,
                "role": user.role,
            },
            "must_change_password": must_change,
        }

    # ------------------------------------------------------------------
    # Token 刷新（轮换策略）
    # ------------------------------------------------------------------

    def refresh_access_token(
        self,
        refresh_token: str,
        ip: str | None = None,
        user_agent: str | None = None,
    ) -> dict:
        """使用 Refresh Token 换取新的 Token 对。

        一次轮换策略:
        1. 验证 Refresh Token
        2. 查找数据库记录
        3. 如果已撤销 → 检测到重放攻击，撤销该用户所有 Token
        4. 撤销旧 Token
        5. 签发新 Token 对
        """
        try:
            payload = verify_refresh_token(refresh_token)
        except Exception:
            raise AuthenticationError("无效的 Refresh Token", status_code=401)

        jti = payload["jti"]
        user_id = int(payload["sub"])

        # 查找数据库记录
        record = self.token_repo.get_by_jti(jti)

        if record is None:
            # Token 记录不存在
            raise AuthenticationError("无效的 Refresh Token", status_code=401)

        # 检测重放攻击：已撤销的 Token 再次使用
        if record.is_revoked:
            logger.warning(
                "检测到已撤销 Refresh Token 再次使用 | jti=%s | user_id=%d",
                jti[:8],
                user_id,
            )
            # 撤销该用户所有 Token（安全措施）
            self.token_repo.revoke_all_for_user(user_id)
            raise AuthenticationError("无效的 Refresh Token", status_code=401)

        if record.is_expired:
            raise AuthenticationError("Refresh Token 已过期，请重新登录", status_code=401)

        # 撤销旧 Token
        self.token_repo.revoke_by_jti(jti)

        # 获取用户
        user = self.user_repo.get_by_id(user_id)
        if user is None or not user.is_active:
            raise AuthenticationError("用户不存在或已被禁用", status_code=403)

        # 签发新 Token 对
        return self.issue_tokens(user, ip, user_agent)

    # ------------------------------------------------------------------
    # 退出
    # ------------------------------------------------------------------

    def logout(self, refresh_token: str) -> None:
        """撤销单个 Refresh Token（单设备退出）。"""
        try:
            payload = decode_token(refresh_token)
        except Exception:
            # Token 无效也视为已退出
            return

        jti = payload.get("jti")
        if jti:
            self.token_repo.revoke_by_jti(jti)

    def logout_all(self, user_id: int) -> int:
        """撤销用户所有 Refresh Token（全部设备退出）。

        Returns
        -------
        int
            被撤销的 Token 数量
        """
        return self.token_repo.revoke_all_for_user(user_id)

    # ------------------------------------------------------------------
    # 修改密码
    # ------------------------------------------------------------------

    def change_password(
        self,
        user: User,
        old_password: str,
        new_password: str,
    ) -> None:
        """修改用户密码。

        1. 验证旧密码
        2. 验证新密码强度
        3. 更新密码哈希
        4. 撤销所有 Refresh Token（强制重新登录）
        """
        # 验证旧密码
        if not verify_password(old_password, user.password_hash):
            raise AuthenticationError("当前密码不正确")

        # 验证新密码强度
        valid, error = validate_password_strength(new_password, user.username)
        if not valid:
            raise AuthenticationError(error or "密码强度不足")

        # 新密码不能与旧密码相同
        if verify_password(new_password, user.password_hash):
            raise AuthenticationError("新密码不能与当前密码相同")

        # 更新密码
        user.password_hash = hash_password(new_password)
        user.password_changed_at = datetime.now(timezone.utc)
        self.user_repo.update(user)

        # 撤销所有 Token（强制重新登录）
        count = self.token_repo.revoke_all_for_user(user.id)
        logger.info(
            "密码已修改，已撤销 %d 个 Refresh Token | user_id=%d",
            count,
            user.id,
        )

    # ------------------------------------------------------------------
    # 获取当前用户
    # ------------------------------------------------------------------

    def get_current_user_info(self, user_id: int) -> dict:
        """获取当前用户安全信息。"""
        user = self.user_repo.get_by_id(user_id)
        if user is None:
            raise AuthenticationError("用户不存在", status_code=404)

        return {
            "id": user.id,
            "username": user.username,
            "display_name": user.display_name,
            "email": user.email,
            "role": user.role,
            "is_active": user.is_active,
            "is_superuser": user.is_superuser,
            "last_login_at": user.last_login_at.isoformat() if user.last_login_at else None,
            "created_at": user.created_at.isoformat() if user.created_at else None,
        }


# ---------------------------------------------------------------------------
# 自定义异常
# ---------------------------------------------------------------------------


class AuthenticationError(Exception):
    """认证错误 — 统一使用此异常以返回安全错误消息。"""

    def __init__(self, message: str, status_code: int = 401):
        self.message = message
        self.status_code = status_code
        super().__init__(message)
