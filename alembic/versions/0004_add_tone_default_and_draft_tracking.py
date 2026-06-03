"""add tone default to businesses and draft tracking to alert_logs

Revision ID: 0004
Revises: 0003
Create Date: 2026-06-03

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0004"
down_revision: Union[str, None] = "0003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Set tone default on businesses (backfill nulls, then add server default)
    op.execute("UPDATE businesses SET tone = 'cercano' WHERE tone IS NULL")
    op.alter_column(
        "businesses",
        "tone",
        existing_type=sa.String(50),
        nullable=False,
        server_default="cercano",
    )

    # Add draft tracking fields to alert_logs
    op.add_column(
        "alert_logs",
        sa.Column("draft_type", sa.String(20), nullable=True),
    )
    op.add_column(
        "alert_logs",
        sa.Column("ai_draft_tokens", sa.Integer(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("alert_logs", "ai_draft_tokens")
    op.drop_column("alert_logs", "draft_type")
    op.alter_column(
        "businesses",
        "tone",
        existing_type=sa.String(50),
        nullable=True,
        server_default=None,
    )
