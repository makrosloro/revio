from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, ForeignKey, String, Text, TIMESTAMP, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.user import User
    from app.models.review import Review


class Business(Base):
    __tablename__ = "businesses"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(String(255))
    google_place_id: Mapped[str] = mapped_column(String(255), index=True)
    platform: Mapped[str] = mapped_column(String(50), server_default="google")
    is_paused: Mapped[bool] = mapped_column(Boolean, server_default="false")
    self_declared_owner: Mapped[bool] = mapped_column(Boolean, server_default="false")
    tone: Mapped[str] = mapped_column(String(50), server_default="cercano")

    # Google Business Profile (GBP) — set once the owner links their Google account
    gbp_account_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    gbp_location_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    gbp_access_token: Mapped[str | None] = mapped_column(Text, nullable=True)
    gbp_refresh_token: Mapped[str | None] = mapped_column(Text, nullable=True)
    gbp_token_expires_at: Mapped[datetime | None] = mapped_column(
        TIMESTAMP(timezone=True), nullable=True
    )

    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=func.now()
    )

    user: Mapped["User"] = relationship(back_populates="businesses")
    reviews: Mapped[list["Review"]] = relationship(
        back_populates="business", cascade="all, delete-orphan"
    )
