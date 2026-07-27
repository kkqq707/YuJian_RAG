"""phase7_add_module_status_and_system_settings

Revision ID: d7b8c9e0f1a2
Revises: d0305b37c718
Create Date: 2026-07-15 14:15:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd7b8c9e0f1a2'
down_revision: Union[str, None] = 'd0305b37c718'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. 添加 module 和 status 列到 admin_audit_logs
    with op.batch_alter_table('admin_audit_logs', schema=None) as batch_op:
        batch_op.add_column(sa.Column('module', sa.String(length=50), nullable=True))
        batch_op.add_column(sa.Column('status', sa.String(length=20), nullable=True, server_default='success'))
        batch_op.create_index(batch_op.f('ix_admin_audit_logs_module'), ['module'], unique=False)

    # 2. 创建 system_settings 表
    op.create_table('system_settings',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('key', sa.String(length=255), nullable=False),
        sa.Column('value', sa.Text(), nullable=False, server_default=''),
        sa.Column('type', sa.String(length=50), nullable=False, server_default='string'),
        sa.Column('description', sa.String(length=500), nullable=True, server_default=''),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('system_settings', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_system_settings_key'), ['key'], unique=True)


def downgrade() -> None:
    # 1. 移除 system_settings 表
    with op.batch_alter_table('system_settings', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_system_settings_key'))
    op.drop_table('system_settings')

    # 2. 移除 admin_audit_logs 的 module 和 status 列
    with op.batch_alter_table('admin_audit_logs', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_admin_audit_logs_module'))
        batch_op.drop_column('status')
        batch_op.drop_column('module')
