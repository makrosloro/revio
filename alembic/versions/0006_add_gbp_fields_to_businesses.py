"""add Google Business Profile fields to businesses

Revision ID: 0006
Revises: 0005
Create Date: 2026-06-03

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0006"
down_revision: Union[str, None] = "0005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("businesses", sa.Column("gbp_account_name", sa.String(255), nullable=True))
    op.add_column("businesses", sa.Column("gbp_location_name", sa.String(255), nullable=True))
    op.add_column("businesses", sa.Column("gbp_access_token", sa.Text(), nullable=True))
    op.add_column("businesses", sa.Column("gbp_refresh_token", sa.Text(), nullable=True))
    op.add_column(
        "businesses",
        sa.Column("gbp_token_expires_at", sa.TIMESTAMP(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("businesses", "gbp_token_expires_at")
    op.drop_column("businesses", "gbp_refresh_token")
    op.drop_column("businesses", "gbp_access_token")
    op.drop_column("businesses", "gbp_location_name")
    op.drop_column("businesses", "gbp_account_name")
