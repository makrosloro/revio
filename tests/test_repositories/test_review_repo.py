"""Tests for app/repositories/review_repo.py — Agent 03."""
from datetime import date, datetime, timezone

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.business import Business
from app.models.review import Review
from app.models.user import User
from app.repositories import review_repo


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _insert_review(
    db_session: AsyncSession,
    business: Business,
    *,
    review_id: str = "rev_001",
    platform: str = "google",
    rating: int = 2,
    review_type: str = "negative",
    digest_sent_at: datetime | None = None,
) -> Review:
    review = Review(
        business_id=business.id,
        review_id=review_id,
        platform=platform,
        rating=rating,
        author_name="Test Author",
        text="Texto de prueba",
        sentiment=review_type,
        review_type=review_type,
        digest_sent_at=digest_sent_at,
    )
    db_session.add(review)
    await db_session.commit()
    await db_session.refresh(review)
    return review


# ---------------------------------------------------------------------------
# exists
# ---------------------------------------------------------------------------

async def test_exists_returns_true_for_known_review(
    db_session: AsyncSession, test_business: Business
) -> None:
    await _insert_review(db_session, test_business, review_id="rev_exists", platform="google")
    result = await review_repo.exists(db_session, "google", "rev_exists")
    assert result is True


async def test_exists_returns_false_for_unknown_review(db_session: AsyncSession) -> None:
    result = await review_repo.exists(db_session, "google", "nonexistent_rev")
    assert result is False


async def test_exists_same_id_different_platform_returns_false(
    db_session: AsyncSession, test_business: Business
) -> None:
    await _insert_review(db_session, test_business, review_id="rev_x", platform="google")
    result = await review_repo.exists(db_session, "tripadvisor", "rev_x")
    assert result is False


# ---------------------------------------------------------------------------
# create
# ---------------------------------------------------------------------------

async def test_create_saves_all_fields(
    db_session: AsyncSession, test_business: Business
) -> None:
    published = datetime(2026, 6, 1, 12, 0, 0)
    review = await review_repo.create(
        db_session,
        business_id=test_business.id,
        platform="google",
        review_id="rev_create_001",
        rating=2,
        text="Muy mal servicio",
        author="María García",
        reviewed_at=published,
        review_type="negative",
    )
    assert review.id is not None
    assert review.business_id == test_business.id
    assert review.review_id == "rev_create_001"
    assert review.platform == "google"
    assert review.rating == 2
    assert review.text == "Muy mal servicio"
    assert review.author_name == "María García"
    assert review.review_type == "negative"
    assert review.sentiment == "negative"
    assert review.digest_sent_at is None


async def test_create_positive_review_type(
    db_session: AsyncSession, test_business: Business
) -> None:
    review = await review_repo.create(
        db_session,
        business_id=test_business.id,
        platform="google",
        review_id="rev_pos_001",
        rating=5,
        text="Excelente",
        author="Carlos L.",
        reviewed_at=None,
        review_type="positive",
    )
    assert review.review_type == "positive"
    assert review.rating == 5


# ---------------------------------------------------------------------------
# get_recent_negatives — data isolation critical path
# ---------------------------------------------------------------------------

async def test_get_recent_negatives_returns_only_target_business(
    db_session: AsyncSession,
    test_business: Business,
    test_user: User,
    test_user_other: User,
) -> None:
    """A user must NOT see negatives that belong to another user's business."""
    from app.models.business import Business as BusinessModel

    other_biz = BusinessModel(
        user_id=test_user_other.id,
        name="Restaurante Ajeno",
        google_place_id="ChIJother2",
    )
    db_session.add(other_biz)
    await db_session.commit()
    await db_session.refresh(other_biz)

    await _insert_review(db_session, test_business, review_id="neg_mine", review_type="negative")
    await _insert_review(db_session, other_biz, review_id="neg_other", review_type="negative")

    results = await review_repo.get_recent_negatives(
        db_session, test_business.id, test_user.id
    )
    ids = [r.review_id for r in results]
    assert "neg_mine" in ids
    assert "neg_other" not in ids


async def test_get_recent_negatives_excludes_positives(
    db_session: AsyncSession, test_business: Business, test_user: User
) -> None:
    await _insert_review(db_session, test_business, review_id="neg_001", review_type="negative")
    await _insert_review(db_session, test_business, review_id="pos_001", review_type="positive", rating=5)

    results = await review_repo.get_recent_negatives(db_session, test_business.id, test_user.id)
    assert all(r.review_type == "negative" for r in results)


async def test_get_recent_negatives_respects_limit(
    db_session: AsyncSession, test_business: Business, test_user: User
) -> None:
    for i in range(8):
        await _insert_review(
            db_session, test_business, review_id=f"neg_{i:02d}", review_type="negative"
        )
    results = await review_repo.get_recent_negatives(db_session, test_business.id, test_user.id, limit=5)
    assert len(results) == 5


# ---------------------------------------------------------------------------
# get_undigested_positives
# ---------------------------------------------------------------------------

async def test_get_undigested_positives_returns_undigested(
    db_session: AsyncSession, test_business: Business, test_user: User
) -> None:
    await _insert_review(
        db_session, test_business, review_id="pos_undigested", review_type="positive", rating=5
    )
    results = await review_repo.get_undigested_positives(
        db_session, test_business.id, test_user.id, date.today()
    )
    ids = [r.review_id for r in results]
    assert "pos_undigested" in ids


async def test_get_undigested_positives_excludes_already_sent(
    db_session: AsyncSession, test_business: Business, test_user: User
) -> None:
    await _insert_review(
        db_session,
        test_business,
        review_id="pos_already_sent",
        review_type="positive",
        rating=4,
        digest_sent_at=datetime(2026, 6, 3, 10, 0, 0),
    )
    results = await review_repo.get_undigested_positives(
        db_session, test_business.id, test_user.id, date.today()
    )
    ids = [r.review_id for r in results]
    assert "pos_already_sent" not in ids


async def test_get_undigested_positives_excludes_negatives(
    db_session: AsyncSession, test_business: Business, test_user: User
) -> None:
    await _insert_review(
        db_session, test_business, review_id="neg_skip", review_type="negative", rating=2
    )
    results = await review_repo.get_undigested_positives(
        db_session, test_business.id, test_user.id, date.today()
    )
    ids = [r.review_id for r in results]
    assert "neg_skip" not in ids


# ---------------------------------------------------------------------------
# mark_digest_sent
# ---------------------------------------------------------------------------

async def test_mark_digest_sent_updates_timestamp(
    db_session: AsyncSession, test_business: Business
) -> None:
    review = await _insert_review(
        db_session, test_business, review_id="pos_to_mark", review_type="positive"
    )
    assert review.digest_sent_at is None

    await review_repo.mark_digest_sent(db_session, [review.id])

    await db_session.refresh(review)
    assert review.digest_sent_at is not None


async def test_mark_digest_sent_empty_list_is_noop(db_session: AsyncSession) -> None:
    # Should not raise
    await review_repo.mark_digest_sent(db_session, [])
