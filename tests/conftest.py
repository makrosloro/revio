import os

# Set test environment variables BEFORE any app import to avoid pydantic-settings validation errors
os.environ.setdefault("TELEGRAM_BOT_TOKEN", "test_token_xxx")
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///:memory:")
os.environ.setdefault("WEBHOOK_URL", "https://test.example.com")
os.environ.setdefault("GOOGLE_PLACES_API_KEY", "test_google_key")
os.environ.setdefault("STRIPE_SECRET_KEY", "sk_test_xxx")
os.environ.setdefault("STRIPE_WEBHOOK_SECRET", "whsec_xxx")
os.environ.setdefault("STRIPE_PRO_PRICE_ID", "price_pro_xxx")
os.environ.setdefault("STRIPE_MULTI_PRICE_ID", "price_multi_xxx")
os.environ.setdefault("ANTHROPIC_API_KEY", "test_anthropic_key")
os.environ.setdefault("BOT_ADMIN_CHAT_ID", "123456")

from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.database import Base
from app.models.business import Business
from app.models.review import Review
from app.models.user import User


@pytest.fixture
async def db_session():
    """Isolated in-memory SQLite session, created fresh for each test."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with session_factory() as session:
        yield session

    await engine.dispose()


@pytest.fixture
async def test_user(db_session: AsyncSession) -> User:
    """Pro user with active subscription and linked telegram_user_id."""
    user = User(
        email="test@example.com",
        telegram_user_id=123456789,
        stripe_customer_id="cus_test123",
        stripe_subscription_id="sub_test123",
        plan="pro",
        sub_status="active",
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest.fixture
async def test_user_free(db_session: AsyncSession) -> User:
    """Free plan user."""
    user = User(
        email="free@example.com",
        telegram_user_id=987654321,
        plan="free",
        sub_status="active",
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest.fixture
async def test_user_other(db_session: AsyncSession) -> User:
    """A second, unrelated Pro user used for data-isolation tests."""
    user = User(
        email="other@example.com",
        telegram_user_id=111222333,
        plan="pro",
        sub_status="active",
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest.fixture
async def test_business(db_session: AsyncSession, test_user: User) -> Business:
    """Active business owned by test_user."""
    business = Business(
        user_id=test_user.id,
        name="Restaurante Test",
        google_place_id="ChIJtest123",
        is_paused=False,
    )
    db_session.add(business)
    await db_session.commit()
    await db_session.refresh(business)
    return business


@pytest.fixture
def mock_bot_app() -> MagicMock:
    """Mock of the python-telegram-bot Application."""
    app = MagicMock()
    app.bot.send_message = AsyncMock(return_value=MagicMock(message_id=42))
    return app


@pytest.fixture
def mock_session_cm():
    """Returns (context-manager factory, mock session) for patching AsyncSessionLocal."""
    mock_session = MagicMock()

    @asynccontextmanager
    async def _session_local():
        yield mock_session

    return _session_local, mock_session
