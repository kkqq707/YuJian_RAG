"""rag3_add_rag_configs_table

Revision ID: e8f9a0b1c2d3
Revises: d7b8c9e0f1a2
Create Date: 2026-07-16 12:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e8f9a0b1c2d3'
down_revision: Union[str, None] = 'd7b8c9e0f1a2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'rag_configs',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('chunk_size', sa.Integer(), nullable=False, server_default='500'),
        sa.Column('chunk_overlap', sa.Integer(), nullable=False, server_default='100'),
        sa.Column('top_k', sa.Integer(), nullable=False, server_default='4'),
        sa.Column('similarity_threshold', sa.Float(), nullable=False, server_default='0.32'),
        sa.Column('hybrid_fetch_k', sa.Integer(), nullable=False, server_default='20'),
        sa.Column('vector_weight', sa.Float(), nullable=False, server_default='0.7'),
        sa.Column('keyword_weight', sa.Float(), nullable=False, server_default='0.3'),
        sa.Column('rerank_enable', sa.Boolean(), nullable=False, server_default=sa.text('1')),
        sa.Column('rerank_fetch_k', sa.Integer(), nullable=False, server_default='20'),
        sa.Column('rerank_top_k', sa.Integer(), nullable=False, server_default='5'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )


def downgrade() -> None:
    op.drop_table('rag_configs')
