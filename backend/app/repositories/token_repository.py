"""Refresh Token 数据仓库

- 数据库不保存完整 Refresh Token 明文
- 保存 Token 的安全哈希
- 支持按 jti / user_id 撤销
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.models.refresh_token import RefreshToken


class TokenRepository:
    """Refresh Token 数据访问。"""

    def __init__(self, db: Session):
        self.db = db

    def create(
        self,
        user_id: int,
        token_jti: str,
        token_hash: str,
        expires_at: datetime,
        created_ip: str | None = None,
        user_agent: str | None = None,
    ) -> RefreshToken:
        """创建 Refresh Token 记录。"""
        record = RefreshToken(
            user_id=user_id,
            token_jti=token_jti,
            token_hash=token_hash,
            expires_at=expires_at,
            created_ip=created_ip,
            user_agent=user_agent,
        )
        self.db.add(record)
        self.db.flush()
        self.db.refresh(record)
        return record

    def get_by_jti(self, jti: str) -> RefreshToken | None:
        """按 jti 查询。"""
        stmt = select(RefreshToken).where(RefreshToken.token_jti == jti)
        return self.db.execute(stmt).scalar_one_or_none()

    def get_by_hash(self, token_hash: str) -> RefreshToken | None:
        """按哈希查询有效 Token。"""
        stmt = select(RefreshToken).where(RefreshToken.token_hash == token_hash)
        return self.db.execute(stmt).scalar_one_or_none()

    def revoke_by_jti(self, jti: str) -> None:
        """撤销单个 Token。"""
        record = self.get_by_jti(jti)
        if record and not record.is_revoked:
            record.revoke()
            self.db.flush()

    def revoke_all_for_user(self, user_id: int) -> int:
        """撤销某用户所有未撤销的 Refresh Token。

        Returns
        -------
        int
            被撤销的 Token 数量
        """
        stmt = select(RefreshToken).where(
            RefreshToken.user_id == user_id,
            RefreshToken.revoked_at.is_(None),
        )
        records = self.db.execute(stmt).scalars().all()
        count = 0
        for record in records:
            record.revoke()
            count += 1
        if count > 0:
            self.db.flush()
        return count

    def delete_expired(self, before: datetime | None = None) -> int:
        """删除过期的 Token 记录（用于定期清理）。

        Parameters
        ----------
        before : datetime | None
            删除此时间之前过期的 Token，默认为当前 UTC 时间

        Returns
        -------
        int
            被删除的记录数
        """
        if before is None:
            before = datetime.now(timezone.utc)

        stmt = select(RefreshToken).where(RefreshToken.expires_at < before)
        records = self.db.execute(stmt).scalars().all()
        count = 0
        for record in records:
            self.db.delete(record)
            count += 1
        if count > 0:
            self.db.flush()
        return count
