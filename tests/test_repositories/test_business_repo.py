"""Tests for app/repositories/business_repo.py — Agent 03."""
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.business import Business
from app.models.user import User
from app.repositories import business_repo


@pytest.fixture
async def paused_business(db_session: AsyncSession, test_user: User) -> Business:
    business = Business(
        user_id=test_user.id,
        name="Negocio Pausado",
        google_place_id="ChIJpaused",
        is_paused=True,
    )
    db_session.add(business)
    await db_session.commit()
    await db_session.refresh(business)
    return business


@pytest.fixture
async def other_business(db_session: AsyncSession, test_user_other: User) -> Business:
    business = Business(
        user_id=test_user_other.id,
        name="Negocio Ajeno",
        google_place_id="ChIJother",
        is_paused=False,
    )
    db_session.add(business)
    await db_session.commit()
    await db_session.refresh(business)
    return business


# ---------------------------------------------------------------------------
# get_all_active
# ---------------------------------------------------------------------------

async def test_get_all_active_returns_non_paused(
    db_session: AsyncSession, test_business: Business, paused_business: Business
) -> None:
    results = await business_repo.get_all_active(db_session)
    ids = [b.id for b in results]
    assert test_business.id in ids
    assert paused_business.id not in ids


async def test_get_all_active_eager_loads_user(
    db_session: AsyncSession, test_business: Business
) -> None:
    results = await business_repo.get_all_active(db_session)
    assert results, "Expected at least one active business"
    # The user relationship must be loaded (no lazy-load exception)
    assert results[0].user is not None
    assert results[0].user.email == "test@example.com"


async def test_get_all_active_excludes_other_users_businesses(
    db_session: AsyncSession,
    test_business: Business,
    other_business: Business,
) -> None:
    results = await business_repo.get_all_active(db_session)
    # Both users' active businesses are returned (get_all_active is global)
    ids = [b.id for b in results]
    assert test_business.id in ids
    assert other_business.id in ids


# ---------------------------------------------------------------------------
# get_by_id — data isolation critical path
# ---------------------------------------------------------------------------

async def test_get_by_id_correct_user_returns_business(
    db_session: AsyncSession, test_business: Business, test_user: User
) -> None:
    result = await business_repo.get_by_id(db_session, test_business.id, test_user.id)
    assert result is not None
    assert result.id == test_business.id


async def test_get_by_id_wrong_user_returns_none(
    db_session: AsyncSession, test_business: Business, test_user_other: User
) -> None:
    """CRITICAL: a user must NOT be able to access another user's business."""
    result = await business_repo.get_by_id(db_session, test_business.id, test_user_other.id)
    assert result is None


async def test_get_by_id_nonexistent_returns_none(
    db_session: AsyncSession, test_user: User
) -> None:
    result = await business_repo.get_by_id(db_session, 99999, test_user.id)
    assert result is None


# ---------------------------------------------------------------------------
# set_active
# ---------------------------------------------------------------------------

async def test_set_active_false_pauses_business(
    db_session: AsyncSession, test_business: Business, test_user: User
) -> None:
    await business_repo.set_active(db_session, test_business.id, test_user.id, active=False)
    result = await business_repo.get_by_id(db_session, test_business.id, test_user.id)
    assert result is not None
    assert result.is_paused is True


async def test_set_active_true_resumes_business(
    db_session: AsyncSession, paused_business: Business, test_user: User
) -> None:
    await business_repo.set_active(db_session, paused_business.id, test_user.id, active=True)
    result = await business_repo.get_by_id(db_session, paused_business.id, test_user.id)
    assert result is not None
    assert result.is_paused is False


async def test_set_active_wrong_user_has_no_effect(
    db_session: AsyncSession, test_business: Business, test_user: User
) -> None:
    wrong_user_id = test_user.id + 99999  # guaranteed not to match
    await business_repo.set_active(db_session, test_business.id, wrong_user_id, active=False)
    result = await business_repo.get_by_id(db_session, test_business.id, test_user.id)
    assert result is not None
    assert result.is_paused is False  # unchanged
