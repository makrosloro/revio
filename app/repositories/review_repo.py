import logging
from datetime import date, datetime, timezone

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.review import Review

logger = logging.getLogger(__name__)


async def exists(session: AsyncSession, platform: str, review_id: str) -> bool:
    result = await session.execute(
        select(Review.id).where(Review.platform == platform, Review.review_id == review_id)
    )
    return result.scalar_one_or_none() is not None


async def create(
    session: AsyncSession,
    business_id: int,
    platform: str,
    review_id: str,
    rating: int,
    text: str | None,
    author: str,
    reviewed_at: datetime | None,
    review_type: str,
) -> Review:
    review = Review(
        business_id=business_id,
        platform=platform,
        review_id=review_id,
        rating=rating,
        text=text,
        author_name=author,
        published_at=reviewed_at,
        review_type=review_type,
        sentiment=review_type,
    )
    session.add(review)
    await session.commit()
    await session.refresh(review)
    return review


async def get_undigested_positives(
    session: AsyncSession, business_id: int, user_id: int, for_date: date
) -> list[Review]:
    """Return positive reviews for the given date that have not yet been included in a digest."""
    from app.models.business import Business

    day_start = datetime(for_date.year, for_date.month, for_date.day, tzinfo=timezone.utc)
    day_end = datetime(for_date.year, for_date.month, for_date.day, 23, 59, 59, tzinfo=timezone.utc)

    result = await session.execute(
        select(Review)
        .join(Business, Review.business_id == Business.id)
        .where(
            Review.business_id == business_id,
            Business.user_id == user_id,
            Review.review_type == "positive",
            Review.digest_sent_at.is_(None),
            Review.created_at >= day_start,
            Review.created_at <= day_end,
        )
        .order_by(Review.rating.desc(), Review.created_at)
    )
    return list(result.scalars().all())


async def mark_digest_sent(session: AsyncSession, review_ids: list[int]) -> None:
    if not review_ids:
        return
    await session.execute(
        update(Review)
        .where(Review.id.in_(review_ids))
        .values(digest_sent_at=datetime.now(tz=timezone.utc))
    )
    await session.commit()


async def get_recent_negatives(
    session: AsyncSession, business_id: int, user_id: int, limit: int = 10
) -> list[Review]:
    from app.models.business import Business

    result = await session.execute(
        select(Review)
        .join(Business, Review.business_id == Business.id)
        .where(
            Review.business_id == business_id,
            Business.user_id == user_id,
            Review.review_type == "negative",
        )
        .order_by(Review.created_at.desc())
        .limit(limit)
    )
    return list(result.scalars().all())
