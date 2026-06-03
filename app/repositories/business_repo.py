from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.business import Business

PLAN_LIMITS = {"free": 0, "pro": 1, "multi": 3}


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
    session: AsyncSession, user_id: int, name: str, google_place_id: str
) -> Business:
    business = Business(user_id=user_id, name=name, google_place_id=google_place_id)
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
