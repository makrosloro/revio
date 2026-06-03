"""add review_type and digest_sent_at to reviews

Revision ID: 0003
Revises: 0002
Create Date: 2026-06-03

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0003"
down_revision: Union[str, None] = "0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "reviews",
        sa.Column(
            "review_type",
            sa.String(20),
            server_default="negative",
            nullable=False,
        ),
    )
    op.add_column(
        "reviews",
        sa.Column("digest_sent_at", sa.TIMESTAMP(timezone=True), nullable=True),
    )
    op.create_index(
        "ix_reviews_business_type_digest",
        "reviews",
        ["business_id", "review_type", "digest_sent_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_reviews_business_type_digest", "reviews")
    op.drop_column("reviews", "digest_sent_at")
    op.drop_column("reviews", "review_type")
