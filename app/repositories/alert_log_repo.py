from sqlalchemy.ext.asyncio import AsyncSession

from app.models.alert_log import AlertLog


async def create(
    session: AsyncSession,
    review_id: int,
    telegram_message_id: int | None,
    alert_type: str,
) -> AlertLog:
    log = AlertLog(
        review_id=review_id,
        telegram_message_id=telegram_message_id,
        alert_type=alert_type,
    )
    session.add(log)
    await session.commit()
    await session.refresh(log)
    return log
