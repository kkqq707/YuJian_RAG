"""管理员初始化脚本

运行方式:
    .venv/Scripts/python.exe backend/scripts/create_admin.py

功能:
- 检查 admin 用户是否存在
- 不存在则使用固定测试账号创建
- 已存在则提示不覆盖

安全:
- 密码使用 bcrypt 哈希存储
- 不通过命令行参数传递密码
- 不在日志中记录密码
"""

from __future__ import annotations

import os
import sys

_PROJECT_ROOT = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..")
)
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from backend.app.database import SessionLocal, engine
from backend.app.models.base import Base
from backend.app.models.user import User
from backend.app.security.password import hash_password
from backend.config.test_accounts import (
    ADMIN_USERNAME,
    ADMIN_PASSWORD,
    guard_production,
)


def _ensure_tables():
    """确保数据库表已创建。"""
    Base.metadata.create_all(bind=engine)


def main():
    """主入口。"""
    # 生产环境保护
    guard_production()

    _ensure_tables()
    db = SessionLocal()

    try:
        print("=" * 60)
        print("  管理员账户初始化")
        print("=" * 60)
        print()

        # 检查用户是否已存在
        existing = (
            db.query(User)
            .filter(User.username == ADMIN_USERNAME)
            .first()
        )

        if existing:
            print(f"用户 '{existing.username}' 已存在，不覆盖。")
            print(f"  ID: {existing.id}")
            print(f"  角色: {existing.role}")
            print(f"  超级管理员: {existing.is_superuser}")
            print(f"  激活状态: {existing.is_active}")
            return

        # 创建固定管理员账号
        user = User(
            username=ADMIN_USERNAME,
            display_name="系统管理员",
            email=None,
            password_hash=hash_password(ADMIN_PASSWORD),
            role="admin",
            is_superuser=True,
            is_active=True,
        )

        db.add(user)
        db.commit()
        db.refresh(user)

        print("[OK] 管理员账户创建成功!")
        print(f"  用户 ID: {user.id}")
        print(f"  用户名: {user.username}")
        print(f"  密码:   {ADMIN_PASSWORD}")
        print(f"  角色:   {user.role}")
        print(f"  超级管理员: {user.is_superuser}")
        print()
        print("[WARN] 默认密码为固定测试密码，建议首次登录后修改。")

    except Exception as e:
        db.rollback()
        print(f"\n[ERROR] 创建失败: {e}")
        sys.exit(1)
    finally:
        db.close()


if __name__ == "__main__":
    main()
