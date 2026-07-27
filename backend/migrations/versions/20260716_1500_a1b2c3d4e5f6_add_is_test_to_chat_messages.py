"""add_is_test_to_chat_messages (merge)

Revision ID: a1b2c3d4e5f6
Revises: e8f9a0b1c2d3, f1a2b3c4d5e6
Create Date: 2026-07-16 15:00:00.000000

为 chat_messages 表添加 is_test 字段，用于标记管理员调试/测试消息。
工作台统计排除 is_test=True 的消息。

此迁移合并了两个分支:
- e8f9a0b1c2d3: rag3_add_rag_configs_table
- f1a2b3c4d5e6: rag3_add_relevance_threshold_fields
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, tuple[str, ...], None] = ('e8f9a0b1c2d3', 'f1a2b3c4d5e6')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table('chat_messages', schema=None) as batch_op:
        batch_op.add_column(
            sa.Column(
                'is_test',
                sa.Boolean(),
                nullable=False,
                server_default=sa.text('0'),
                comment='是否为测试消息（管理员调试模式），工作台统计排除此类消息',
            )
        )


def downgrade() -> None:
    with op.batch_alter_table('chat_messages', schema=None) as batch_op:
        batch_op.drop_column('is_test')
