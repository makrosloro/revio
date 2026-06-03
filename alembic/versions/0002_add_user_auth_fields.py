"""add user auth fields

Revision ID: 0002
Revises: 0001
Create Date: 2026-06-03

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0002"
down_revision: Union[str, None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # telegram_user_id nullable: usuarios se crean desde Stripe antes del /activar
    op.alter_column("users", "telegram_user_id", nullable=True)
    op.add_column("users", sa.Column("email", sa.String(255), nullable=True))
    op.add_column(
        "users",
        sa.Column("sub_status", sa.String(20), server_default="active", nullable=False),
    )
    op.add_column(
        "users",
        sa.Column("token_expires_at", sa.TIMESTAMP(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("users", "token_expires_at")
    op.drop_column("users", "sub_status")
    op.drop_column("users", "email")
    op.alter_column("users", "telegram_user_id", nullable=False)
