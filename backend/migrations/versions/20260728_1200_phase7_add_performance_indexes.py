"""phase7_add_performance_indexes

Revision ID: 7a8b9c0d1e2f
Revises: a1b2c3d4e5f6
Create Date: 2026-07-28 12:00:00.000000

为核心表添加复合索引和单列索引，优化查询性能：
1. chat_sessions(user_id, updated_at)  - 按更新时间分页列出用户会话
2. chat_sessions(user_id, created_at)  - 按创建时间列出用户会话
3. chat_messages(session_id, created_at) - 按时间排序获取会话消息
4. admin_audit_logs(created_at) - 审计日志时间范围过滤
5. refresh_tokens(token_hash) - 令牌哈希查找（已在初始迁移中创建，此处验证）
6. chat_messages(role) - 按角色（user/assistant）过滤统计
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '7a8b9c0d1e2f'
down_revision: Union[str, None] = 'a1b2c3d4e5f6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. 复合索引: chat_sessions(user_id, updated_at)
    with op.batch_alter_table('chat_sessions', schema=None) as batch_op:
        batch_op.create_index(
            batch_op.f('ix_chat_sessions_user_id_updated_at'),
            ['user_id', 'updated_at'],
            unique=False,
        )

    # 2. 复合索引: chat_sessions(user_id, created_at)
    with op.batch_alter_table('chat_sessions', schema=None) as batch_op:
        batch_op.create_index(
            batch_op.f('ix_chat_sessions_user_id_created_at'),
            ['user_id', 'created_at'],
            unique=False,
        )

    # 3. 复合索引: chat_messages(session_id, created_at)
    with op.batch_alter_table('chat_messages', schema=None) as batch_op:
        batch_op.create_index(
            batch_op.f('ix_chat_messages_session_id_created_at'),
            ['session_id', 'created_at'],
            unique=False,
        )

    # 4. 单列索引: admin_audit_logs(created_at)
    with op.batch_alter_table('admin_audit_logs', schema=None) as batch_op:
        batch_op.create_index(
            batch_op.f('ix_admin_audit_logs_created_at'),
            ['created_at'],
            unique=False,
        )

    # 5. 单列索引: refresh_tokens(token_hash) —— 初始迁移已创建，
    #    此处用 try/except 兜底，若已存在则跳过。
    try:
        with op.batch_alter_table('refresh_tokens', schema=None) as batch_op:
            batch_op.create_index(
                batch_op.f('ix_refresh_tokens_token_hash'),
                ['token_hash'],
                unique=False,
            )
    except Exception:
        pass

    # 6. 单列索引: chat_messages(role)
    with op.batch_alter_table('chat_messages', schema=None) as batch_op:
        batch_op.create_index(
            batch_op.f('ix_chat_messages_role'),
            ['role'],
            unique=False,
        )


def downgrade() -> None:
    # 1. 删除 chat_sessions(user_id, updated_at)
    with op.batch_alter_table('chat_sessions', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_chat_sessions_user_id_updated_at'))

    # 2. 删除 chat_sessions(user_id, created_at)
    with op.batch_alter_table('chat_sessions', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_chat_sessions_user_id_created_at'))

    # 3. 删除 chat_messages(session_id, created_at)
    with op.batch_alter_table('chat_messages', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_chat_messages_session_id_created_at'))

    # 4. 删除 admin_audit_logs(created_at)
    with op.batch_alter_table('admin_audit_logs', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_admin_audit_logs_created_at'))

    # 5. 删除 refresh_tokens(token_hash)
    with op.batch_alter_table('refresh_tokens', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_refresh_tokens_token_hash'))

    # 6. 删除 chat_messages(role)
    with op.batch_alter_table('chat_messages', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_chat_messages_role'))
