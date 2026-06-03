from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.business import Business

PLAN_LIMITS = {"free": 0, "pro": 1, "multi": 3}


async def get_with_review_counts(session: AsyncSession, user_id: int) -> list[tuple]:
    """Return (Business, review_count) tuples for a user, ordered by creation."""
    from app.models.review import Review

    result = await session.execute(
        select(Business, func.count(Review.id))
        .outerjoin(Review, Review.business_id == Business.id)
        .where(Business.user_id == user_id)
        .group_by(Business.id)
        .order_by(Business.created_at)
    )
    return list(result.all())


async def get_all_active(session: AsyncSession) -> list[Business]:
    """Return all non-paused businesses with their user eagerly loaded."""
    result = await session.execute(
        select(Business)
        .where(Business.is_paused == False)  # noqa: E712 — is_(False) breaks SQLite
        .options(selectinload(Business.user))
        .order_by(Business.id)
    )
    return list(result.scalars().all())


async def get_all_by_user(session: AsyncSession, user_id: int) -> list[Business]:
    result = await session.execute(
        select(Business).where(Business.user_id == user_id).order_by(Business.created_at)
    )
    return list(result.scalars().all())


async def get_by_id(session: AsyncSession, business_id: int, user_id: int) -> Business | None:
    result = await session.execute(
        select(Business).where(Business.id == business_id, Business.user_id == user_id)
    )
    return result.scalar_one_or_none()


async def create(
    session: AsyncSession,
    user_id: int,
    name: str,
    google_place_id: str,
    self_declared_owner: bool = False,
) -> Business:
    business = Business(
        user_id=user_id,
        name=name,
        google_place_id=google_place_id,
        self_declared_owner=self_declared_owner,
    )
    session.add(business)
    await session.commit()
    await session.refresh(business)
    return business


async def toggle_pause(
    session: AsyncSession, business_id: int, user_id: int, is_paused: bool
) -> Business | None:
    await session.execute(
        update(Business)
        .where(Business.id == business_id, Business.user_id == user_id)
        .values(is_paused=is_paused)
    )
    await session.commit()
    return await get_by_id(session, business_id, user_id)


async def count_by_user(session: AsyncSession, user_id: int) -> int:
    result = await session.execute(
        select(func.count()).where(Business.user_id == user_id)
    )
    return result.scalar_one()


async def set_active(
    session: AsyncSession, business_id: int, user_id: int, active: bool
) -> None:
    await session.execute(
        update(Business)
        .where(Business.id == business_id, Business.user_id == user_id)
        .values(is_paused=not active)
    )
    await session.commit()
