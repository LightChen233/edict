"""add governance fields

Revision ID: 002_add_governance
Revises: 001_initial
Create Date: 2026-03-15 00:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "002_add_governance"
down_revision: Union[str, None] = "001_initial"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 扩展 state 字段长度，支持动态状态名
    op.alter_column("tasks", "state",
        existing_type=sa.String(20),
        type_=sa.String(64),
        nullable=False,
    )
    # 新增治理模型字段
    op.add_column("tasks", sa.Column(
        "governance_type", sa.String(32), nullable=False, server_default="san_sheng"
    ))
    op.add_column("tasks", sa.Column(
        "governance_config", postgresql.JSONB(), nullable=False, server_default="{}"
    ))
    op.add_column("tasks", sa.Column(
        "mechanisms", postgresql.JSONB(), nullable=False, server_default="[]"
    ))
    op.create_index("ix_tasks_governance_type", "tasks", ["governance_type"])


def downgrade() -> None:
    op.drop_index("ix_tasks_governance_type", table_name="tasks")
    op.drop_column("tasks", "mechanisms")
    op.drop_column("tasks", "governance_config")
    op.drop_column("tasks", "governance_type")
    op.alter_column("tasks", "state",
        existing_type=sa.String(64),
        type_=sa.String(20),
        nullable=False,
    )
