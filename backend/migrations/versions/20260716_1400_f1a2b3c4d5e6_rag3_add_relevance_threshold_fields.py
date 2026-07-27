"""Phase 2-4: RAG 配置中心 — 添加阈值和查询改写字

Revision ID: f1a2b3c4d5e6
Create Date: 2026-07-16 14:00

增加:
- max_raw_distance: L2 距离上限
- min_relevance_score: 相关度下限
- query_rewrite_enable: 是否启用查询改写
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f1a2b3c4d5e6'
down_revision: Union[str, None] = 'd7b8c9e0f1a2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = 'e8f9a0b1c2d3'


def upgrade() -> None:
    op.add_column('rag_configs', sa.Column(
        'max_raw_distance', sa.Float(), nullable=False, server_default='1.15',
        doc="L2 距离上限（超过此距离视为不相关）"
    ))
    op.add_column('rag_configs', sa.Column(
        'min_relevance_score', sa.Float(), nullable=False, server_default='0.32',
        doc="相关度下限（低于此值视为不相关）"
    ))
    op.add_column('rag_configs', sa.Column(
        'query_rewrite_enable', sa.Boolean(), nullable=False, server_default=sa.text('1'),
        doc="是否启用查询改写"
    ))


def downgrade() -> None:
    op.drop_column('rag_configs', 'query_rewrite_enable')
    op.drop_column('rag_configs', 'min_relevance_score')
    op.drop_column('rag_configs', 'max_raw_distance')
