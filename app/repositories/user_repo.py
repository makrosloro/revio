import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User


async def get_by_telegram_id(session: AsyncSession, telegram_user_id: int) -> User | None:
    result = await session.execute(
        select(User).where(User.telegram_user_id == telegram_user_id)
    )
    return result.scalar_one_or_none()


async def get_by_email(session: AsyncSession, email: str) -> User | None:
    result = await session.execute(
        select(User).where(User.email == email)
    )
    return result.scalar_one_or_none()


async def get_by_activation_token(session: AsyncSession, token: str) -> User | None:
    result = await session.execute(
        select(User).where(User.activation_token == token)
    )
    return result.scalar_one_or_none()


async def create_from_stripe(
    session: AsyncSession,
    email: str,
    stripe_customer_id: str,
    stripe_sub_id: str,
    plan: str,
) -> User:
    token = uuid.uuid4().hex
    expires_at = datetime.now(timezone.utc) + timedelta(hours=48)
    user = User(
        email=email,
        stripe_customer_id=stripe_customer_id,
        stripe_subscription_id=stripe_sub_id,
        plan=plan,
        sub_status="active",
        activation_token=token,
        token_expires_at=expires_at,
    )
    session.add(user)
    await session.commit()
    await session.refresh(user)
    return user


async def activate(session: AsyncSession, user_id: int, telegram_user_id: int) -> User | None:
    """Activate a user account by linking its Telegram ID.

    If another account already uses this telegram_user_id (e.g. a previous free
    signup), merge the paid plan onto that existing account and remove the
    orphan row, so the user keeps their Telegram link and any businesses.
    """
    result = await session.execute(select(User).where(User.id == user_id))
    token_user = result.scalar_one_or_none()
    if not token_user:
        return None

    existing = await get_by_telegram_id(session, telegram_user_id)

    if existing and existing.id != token_user.id:
        # Merge: upgrade the existing (Telegram-linked) account with paid data
        existing.email = token_user.email or existing.email
        existing.stripe_customer_id = token_user.stripe_customer_id or existing.stripe_customer_id
        existing.stripe_subscription_id = (
            token_user.stripe_subscription_id or existing.stripe_subscription_id
        )
        existing.plan = token_user.plan
        existing.sub_status = token_user.sub_status
        existing.activation_token = None
        existing.token_expires_at = None
        existing.is_active = True
        await session.delete(token_user)
        await session.commit()
        await session.refresh(existing)
        return existing

    token_user.telegram_user_id = telegram_user_id
    token_user.activation_token = None
    token_user.token_expires_at = None
    token_user.is_active = True
    await session.commit()
    await session.refresh(token_user)
    return token_user


async def update_subscription(
    session: AsyncSession,
    stripe_sub_id: str,
    sub_status: str,
    plan: str | None = None,
) -> None:
    values: dict = {"sub_status": sub_status}
    if plan:
        values["plan"] = plan
    await session.execute(
        update(User).where(User.stripe_subscription_id == stripe_sub_id).values(**values)
    )
    await session.commit()


async def get_by_stripe_customer(session: AsyncSession, stripe_customer_id: str) -> User | None:
    result = await session.execute(
        select(User).where(User.stripe_customer_id == stripe_customer_id)
    )
    return result.scalar_one_or_none()


async def create_free_user(session: AsyncSession, telegram_user_id: int) -> User:
    """Create a free-plan user directly from Telegram (no Stripe)."""
    user = User(
        telegram_user_id=telegram_user_id,
        plan="free",
        sub_status="active",
        is_active=True,
    )
    session.add(user)
    await session.commit()
    await session.refresh(user)
    return user


async def refresh_activation_token(session: AsyncSession, user_id: int) -> str:
    """Generate a fresh activation token (re-subscriptions or token expiry)."""
    token = uuid.uuid4().hex
    expires_at = datetime.now(timezone.utc) + timedelta(hours=48)
    await session.execute(
        update(User)
        .where(User.id == user_id)
        .values(activation_token=token, token_expires_at=expires_at)
    )
    await session.commit()
    return token


async def get_all_active_subscribers(session: AsyncSession) -> list[User]:
    """Return all active users with a paid plan."""
    result = await session.execute(
        select(User).where(
            User.is_active.is_(True),
            User.plan.in_(("pro", "multi")),
            User.sub_status == "active",
        )
    )
    return list(result.scalars().all())
