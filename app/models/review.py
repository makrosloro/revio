from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Index, Integer, String, Text, TIMESTAMP, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.business import Business
    from app.models.alert_log import AlertLog


class Review(Base):
    __tablename__ = "reviews"

    id: Mapped[int] = mapped_column(primary_key=True)
    business_id: Mapped[int] = mapped_column(
        ForeignKey("businesses.id", ondelete="CASCADE"), index=True
    )
    review_id: Mapped[str] = mapped_column(String(255))
    platform: Mapped[str] = mapped_column(String(50))
    author_name: Mapped[str] = mapped_column(String(255))
    rating: Mapped[int] = mapped_column(Integer)
    text: Mapped[str | None] = mapped_column(Text, nullable=True)
    sentiment: Mapped[str] = mapped_column(String(20))
    published_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=func.now()
    )

    __table_args__ = (
        UniqueConstraint("platform", "review_id", name="uq_platform_review_id"),
        Index("ix_reviews_platform_review_id", "platform", "review_id"),
    )

    business: Mapped["Business"] = relationship(back_populates="reviews")
    alert_logs: Mapped[list["AlertLog"]] = relationship(
        back_populates="review", cascade="all, delete-orphan"
    )
