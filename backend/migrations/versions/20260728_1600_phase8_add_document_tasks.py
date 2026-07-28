"""Phase 8: Add document_tasks table

Revision ID: 20260728_1600_phase8
Revises: 20260728_1200_phase7_add_performance_indexes
Create Date: 2026-07-28 16:00:00
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers
revision: str = 'b1c2d3e4f5a6'
down_revision: Union[str, None] = '7a8b9c0d1e2f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """创建 document_tasks 表。"""
    op.create_table(
        'document_tasks',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('document_id', sa.String(64), nullable=False, index=True),
        sa.Column(
            'task_type',
            sa.String(32),
            nullable=False,
            server_default='index_document',
            comment='index_document | rebuild_document | delete_document_vectors | rebuild_knowledge_base',
        ),
        sa.Column(
            'status',
            sa.String(20),
            nullable=False,
            server_default='pending',
            index=True,
            comment='pending | running | completed | failed | cancel_requested | cancelled',
        ),
        sa.Column('progress', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('current_step', sa.String(128), nullable=True),
        sa.Column('error_code', sa.String(64), nullable=True),
        sa.Column('error_message', sa.String(512), nullable=True),
        sa.Column('created_by', sa.String(64), nullable=False, server_default='admin'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("(datetime('now'))")),
        sa.Column('started_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('cancelled_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('retry_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('original_task_id', sa.Integer(), nullable=True),
        sa.Column('worker_id', sa.String(64), nullable=True),
        sa.Column('heartbeat_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('chunk_count', sa.Integer(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )

    # 复合索引：按文档ID和状态查询
    op.create_index(
        'ix_document_tasks_doc_status',
        'document_tasks',
        ['document_id', 'status'],
    )
    # 创建时间索引（已有 created_at index 但显式添加）
    op.create_index(
        'ix_document_tasks_created_at',
        'document_tasks',
        ['created_at'],
    )


def downgrade() -> None:
    """删除 document_tasks 表。"""
    op.drop_index('ix_document_tasks_created_at')
    op.drop_index('ix_document_tasks_doc_status')
    op.drop_table('document_tasks')
