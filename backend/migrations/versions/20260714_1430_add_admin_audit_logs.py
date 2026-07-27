"""add_admin_audit_logs

Revision ID: 2b3c4d5e6f7a
Revises: 1afa5c2c08bf
Create Date: 2026-07-14 14:30:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '2b3c4d5e6f7a'
down_revision: Union[str, None] = '1afa5c2c08bf'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('admin_audit_logs',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('admin_id', sa.Integer(), nullable=False),
        sa.Column('admin_username', sa.String(length=150), nullable=False),
        sa.Column('action', sa.String(length=50), nullable=False),
        sa.Column('target_type', sa.String(length=50), nullable=True),
        sa.Column('target_id', sa.String(length=255), nullable=True),
        sa.Column('detail', sa.Text(), nullable=True),
        sa.Column('ip_address', sa.String(length=45), nullable=True),
        sa.Column('user_agent', sa.String(length=512), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('admin_audit_logs', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_admin_audit_logs_admin_id'), ['admin_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_admin_audit_logs_action'), ['action'], unique=False)


def downgrade() -> None:
    with op.batch_alter_table('admin_audit_logs', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_admin_audit_logs_action'))
        batch_op.drop_index(batch_op.f('ix_admin_audit_logs_admin_id'))
    op.drop_table('admin_audit_logs')
