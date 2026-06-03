"""Tests for app/services/review_service.py — Agent 03."""
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.models.review import Review
from app.services.review_service import (
    _build_daily_digest,
    _build_negative_alert_free,
    _build_negative_alert_pro,
    _classify_review,
    poll_all_businesses,
    send_daily_digest,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_review(
    *,
    id: int = 1,
    rating: int = 2,
    text: str = "Servicio muy lento.",
    author_name: str = "María G.",
    review_type: str = "negative",
    published_at: datetime | None = None,
) -> MagicMock:
    r = MagicMock(spec=Review)
    r.id = id
    r.rating = rating
    r.text = text
    r.author_name = author_name
    r.review_type = review_type
    r.published_at = published_at
    return r


def _make_business(
    *,
    id: int = 1,
    name: str = "Restaurante Test",
    place_id: str = "ChIJtest",
    plan: str = "pro",
    sub_status: str = "active",
    telegram_user_id: int = 123456789,
    user_id: int = 10,
) -> MagicMock:
    user = MagicMock()
    user.id = user_id
    user.plan = plan
    user.sub_status = sub_status
    user.telegram_user_id = telegram_user_id

    biz = MagicMock()
    biz.id = id
    biz.name = name
    biz.google_place_id = place_id
    biz.is_paused = False
    biz.user = user
    return biz


def _raw_review(
    *,
    name: str = "review_001",
    rating: int = 2,
    text: str = "Muy mal.",
    author: str = "Ana P.",
    publish_time: str | None = None,
) -> dict:
    return {
        "name": name,
        "rating": rating,
        "text": text,
        "authorAttribution": {"displayName": author},
        "publishTime": publish_time,
    }


# ---------------------------------------------------------------------------
# _classify_review
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("rating,expected", [
    (1, "negative"),
    (2, "negative"),
    (3, "negative"),
    (4, "positive"),
    (5, "positive"),
])
def test_classify_review(rating: int, expected: str) -> None:
    assert _classify_review(rating) == expected


# ---------------------------------------------------------------------------
# Message builders
# ---------------------------------------------------------------------------

def test_build_negative_alert_free_contains_upsell() -> None:
    review = _make_review(rating=2, text="Malísimo")
    msg = _build_negative_alert_free("Restaurante Test", review)
    assert "🔴" in msg
    assert "Pro" in msg
    assert "borrador" in msg


def test_build_negative_alert_pro_has_no_upsell() -> None:
    review = _make_review(rating=1, text="Pésimo")
    msg = _build_negative_alert_pro("Restaurante Test", review)
    assert "🔴" in msg
    assert "Pro" not in msg
    assert "borrador" not in msg


def test_build_negative_alert_free_handles_no_text() -> None:
    review = _make_review(text=None)
    msg = _build_negative_alert_free("Restaurante Test", review)
    assert "(sin texto)" in msg


def test_build_daily_digest_shows_business_name_and_count() -> None:
    reviews = [_make_review(id=i, rating=5, text="Genial", review_type="positive") for i in range(3)]
    msg = _build_daily_digest("Mi Bar", reviews)
    assert "🌟" in msg
    assert "Mi Bar" in msg
    assert "3" in msg


def test_build_daily_digest_truncates_at_5_and_shows_extra() -> None:
    reviews = [_make_review(id=i, rating=4, text="Bien", review_type="positive") for i in range(8)]
    msg = _build_daily_digest("Mi Bar", reviews)
    assert "y 3 más" in msg


def test_build_daily_digest_no_extra_line_when_5_or_fewer() -> None:
    reviews = [_make_review(id=i, rating=5, text="Perfecto", review_type="positive") for i in range(5)]
    msg = _build_daily_digest("Mi Bar", reviews)
    assert "más" not in msg


# ---------------------------------------------------------------------------
# poll_all_businesses
# ---------------------------------------------------------------------------

@pytest.fixture
def session_cm_factory():
    """Returns (mock_session_local, mock_session) for patching AsyncSessionLocal."""
    mock_session = MagicMock()

    @asynccontextmanager
    async def _session_local():
        yield mock_session

    return _session_local, mock_session


async def test_poll_new_negative_review_sends_alert(session_cm_factory) -> None:
    cm, _ = session_cm_factory
    biz = _make_business(plan="pro", sub_status="active")
    raw = _raw_review(name="rev_neg_001", rating=2)
    mock_review = _make_review(id=99, rating=2, review_type="negative")
    mock_sent = MagicMock(message_id=42)
    mock_bot_app = MagicMock()
    mock_bot_app.bot.send_message = AsyncMock(return_value=mock_sent)

    with (
        patch("app.services.review_service.AsyncSessionLocal", cm),
        patch("app.repositories.business_repo.get_all_active", AsyncMock(return_value=[biz])),
        patch("app.repositories.review_repo.exists", AsyncMock(return_value=False)),
        patch("app.repositories.review_repo.create", AsyncMock(return_value=mock_review)),
        patch("app.repositories.alert_log_repo.create", AsyncMock()),
        patch("app.services.review_service._places_client") as mock_client,
        patch("app.bot.get_application", return_value=mock_bot_app),
    ):
        mock_client.get_reviews = AsyncMock(return_value=[raw])
        await poll_all_businesses()

    mock_bot_app.bot.send_message.assert_called_once()
    call_kwargs = mock_bot_app.bot.send_message.call_args
    assert call_kwargs.kwargs["chat_id"] == biz.user.telegram_user_id


async def test_poll_new_positive_review_sends_no_alert(session_cm_factory) -> None:
    cm, _ = session_cm_factory
    biz = _make_business(plan="pro")
    raw = _raw_review(name="rev_pos_001", rating=5)
    mock_review = _make_review(id=10, rating=5, review_type="positive")
    mock_bot_app = MagicMock()
    mock_bot_app.bot.send_message = AsyncMock()

    with (
        patch("app.services.review_service.AsyncSessionLocal", cm),
        patch("app.repositories.business_repo.get_all_active", AsyncMock(return_value=[biz])),
        patch("app.repositories.review_repo.exists", AsyncMock(return_value=False)),
        patch("app.repositories.review_repo.create", AsyncMock(return_value=mock_review)),
        patch("app.services.review_service._places_client") as mock_client,
        patch("app.bot.get_application", return_value=mock_bot_app),
    ):
        mock_client.get_reviews = AsyncMock(return_value=[raw])
        await poll_all_businesses()

    mock_bot_app.bot.send_message.assert_not_called()


async def test_poll_existing_review_is_skipped(session_cm_factory) -> None:
    cm, _ = session_cm_factory
    biz = _make_business()
    raw = _raw_review(name="rev_dup_001")
    mock_bot_app = MagicMock()
    mock_bot_app.bot.send_message = AsyncMock()

    with (
        patch("app.services.review_service.AsyncSessionLocal", cm),
        patch("app.repositories.business_repo.get_all_active", AsyncMock(return_value=[biz])),
        patch("app.repositories.review_repo.exists", AsyncMock(return_value=True)),
        patch("app.repositories.review_repo.create") as mock_create,
        patch("app.services.review_service._places_client") as mock_client,
        patch("app.bot.get_application", return_value=mock_bot_app),
    ):
        mock_client.get_reviews = AsyncMock(return_value=[raw])
        await poll_all_businesses()

    mock_create.assert_not_called()
    mock_bot_app.bot.send_message.assert_not_called()


async def test_poll_google_api_error_continues_other_businesses(session_cm_factory) -> None:
    """An exception from Google Places must not block the next business in the loop."""
    cm, _ = session_cm_factory
    biz1 = _make_business(id=1, place_id="ChIJfail")
    biz2 = _make_business(id=2, place_id="ChIJok")
    mock_review = _make_review(id=5, rating=5, review_type="positive")

    with (
        patch("app.services.review_service.AsyncSessionLocal", cm),
        patch("app.repositories.business_repo.get_all_active", AsyncMock(return_value=[biz1, biz2])),
        patch("app.repositories.review_repo.exists", AsyncMock(return_value=False)),
        patch("app.repositories.review_repo.create", AsyncMock(return_value=mock_review)),
        patch("app.services.review_service._places_client") as mock_client,
        patch("app.bot.get_application", return_value=MagicMock()),
    ):
        mock_client.get_reviews = AsyncMock(
            side_effect=[Exception("API error"), [_raw_review(name="rev_ok", rating=5)]]
        )
        await poll_all_businesses()  # must not raise

    assert mock_client.get_reviews.await_count == 2


async def test_poll_free_user_negative_gets_free_format(session_cm_factory) -> None:
    cm, _ = session_cm_factory
    biz = _make_business(plan="free")
    raw = _raw_review(name="rev_free_001", rating=2)
    mock_review = _make_review(id=77, rating=2, review_type="negative")
    mock_sent = MagicMock(message_id=1)
    mock_bot_app = MagicMock()
    mock_bot_app.bot.send_message = AsyncMock(return_value=mock_sent)

    with (
        patch("app.services.review_service.AsyncSessionLocal", cm),
        patch("app.repositories.business_repo.get_all_active", AsyncMock(return_value=[biz])),
        patch("app.repositories.review_repo.exists", AsyncMock(return_value=False)),
        patch("app.repositories.review_repo.create", AsyncMock(return_value=mock_review)),
        patch("app.repositories.alert_log_repo.create", AsyncMock()),
        patch("app.services.review_service._places_client") as mock_client,
        patch("app.bot.get_application", return_value=mock_bot_app),
    ):
        mock_client.get_reviews = AsyncMock(return_value=[raw])
        await poll_all_businesses()

    mock_bot_app.bot.send_message.assert_called_once()
    sent_text = mock_bot_app.bot.send_message.call_args.kwargs["text"]
    assert "Pro" in sent_text  # free format includes upsell


async def test_poll_pro_user_negative_gets_pro_format(session_cm_factory) -> None:
    cm, _ = session_cm_factory
    biz = _make_business(plan="pro", sub_status="active")
    raw = _raw_review(name="rev_pro_001", rating=3)
    mock_review = _make_review(id=88, rating=3, review_type="negative")
    mock_sent = MagicMock(message_id=2)
    mock_bot_app = MagicMock()
    mock_bot_app.bot.send_message = AsyncMock(return_value=mock_sent)

    with (
        patch("app.services.review_service.AsyncSessionLocal", cm),
        patch("app.repositories.business_repo.get_all_active", AsyncMock(return_value=[biz])),
        patch("app.repositories.review_repo.exists", AsyncMock(return_value=False)),
        patch("app.repositories.review_repo.create", AsyncMock(return_value=mock_review)),
        patch("app.repositories.alert_log_repo.create", AsyncMock()),
        patch("app.services.review_service._places_client") as mock_client,
        patch("app.bot.get_application", return_value=mock_bot_app),
    ):
        mock_client.get_reviews = AsyncMock(return_value=[raw])
        await poll_all_businesses()

    sent_text = mock_bot_app.bot.send_message.call_args.kwargs["text"]
    # Pro format must NOT include the upsell message
    assert "Contrata el plan Pro" not in sent_text


# ---------------------------------------------------------------------------
# send_daily_digest
# ---------------------------------------------------------------------------

async def test_send_daily_digest_sends_message_when_positives_exist(
    session_cm_factory,
) -> None:
    cm, _ = session_cm_factory
    user = MagicMock()
    user.id = 1
    user.plan = "pro"
    user.sub_status = "active"
    user.telegram_user_id = 123456789

    biz = MagicMock()
    biz.id = 10
    biz.name = "Mi Restaurante"
    biz.is_paused = False

    positives = [_make_review(id=i, rating=5, review_type="positive") for i in range(2)]
    mock_bot_app = MagicMock()
    mock_bot_app.bot.send_message = AsyncMock()

    with (
        patch("app.services.review_service.AsyncSessionLocal", cm),
        patch("app.repositories.user_repo.get_all_active_subscribers", AsyncMock(return_value=[user])),
        patch("app.repositories.business_repo.get_all_by_user", AsyncMock(return_value=[biz])),
        patch("app.repositories.review_repo.get_undigested_positives", AsyncMock(return_value=positives)),
        patch("app.repositories.review_repo.mark_digest_sent", AsyncMock()),
        patch("app.bot.get_application", return_value=mock_bot_app),
    ):
        await send_daily_digest()

    mock_bot_app.bot.send_message.assert_called_once()
    sent_text = mock_bot_app.bot.send_message.call_args.kwargs["text"]
    assert "🌟" in sent_text
    assert "Mi Restaurante" in sent_text


async def test_send_daily_digest_no_message_when_no_positives(session_cm_factory) -> None:
    cm, _ = session_cm_factory
    user = MagicMock()
    user.id = 1
    user.plan = "pro"
    user.sub_status = "active"
    user.telegram_user_id = 123456789

    biz = MagicMock()
    biz.id = 10
    biz.name = "Mi Bar"
    biz.is_paused = False

    mock_bot_app = MagicMock()
    mock_bot_app.bot.send_message = AsyncMock()

    with (
        patch("app.services.review_service.AsyncSessionLocal", cm),
        patch("app.repositories.user_repo.get_all_active_subscribers", AsyncMock(return_value=[user])),
        patch("app.repositories.business_repo.get_all_by_user", AsyncMock(return_value=[biz])),
        patch("app.repositories.review_repo.get_undigested_positives", AsyncMock(return_value=[])),
        patch("app.bot.get_application", return_value=mock_bot_app),
    ):
        await send_daily_digest()

    mock_bot_app.bot.send_message.assert_not_called()


async def test_send_daily_digest_marks_reviews_as_sent(session_cm_factory) -> None:
    cm, _ = session_cm_factory
    user = MagicMock()
    user.id = 1
    user.plan = "pro"
    user.sub_status = "active"
    user.telegram_user_id = 123456789

    biz = MagicMock()
    biz.id = 10
    biz.name = "Mi Cafetería"
    biz.is_paused = False

    positives = [_make_review(id=i, rating=4, review_type="positive") for i in range(3)]
    mock_mark = AsyncMock()
    mock_bot_app = MagicMock()
    mock_bot_app.bot.send_message = AsyncMock()

    with (
        patch("app.services.review_service.AsyncSessionLocal", cm),
        patch("app.repositories.user_repo.get_all_active_subscribers", AsyncMock(return_value=[user])),
        patch("app.repositories.business_repo.get_all_by_user", AsyncMock(return_value=[biz])),
        patch("app.repositories.review_repo.get_undigested_positives", AsyncMock(return_value=positives)),
        patch("app.repositories.review_repo.mark_digest_sent", mock_mark),
        patch("app.bot.get_application", return_value=mock_bot_app),
    ):
        await send_daily_digest()

    mock_mark.assert_called_once()
    marked_ids = mock_mark.call_args.args[1]
    assert set(marked_ids) == {0, 1, 2}


async def test_send_daily_digest_skips_paused_business(session_cm_factory) -> None:
    cm, _ = session_cm_factory
    user = MagicMock()
    user.id = 1
    user.plan = "pro"
    user.sub_status = "active"
    user.telegram_user_id = 123456789

    paused_biz = MagicMock()
    paused_biz.id = 99
    paused_biz.is_paused = True

    mock_get_positives = AsyncMock()
    mock_bot_app = MagicMock()
    mock_bot_app.bot.send_message = AsyncMock()

    with (
        patch("app.services.review_service.AsyncSessionLocal", cm),
        patch("app.repositories.user_repo.get_all_active_subscribers", AsyncMock(return_value=[user])),
        patch("app.repositories.business_repo.get_all_by_user", AsyncMock(return_value=[paused_biz])),
        patch("app.repositories.review_repo.get_undigested_positives", mock_get_positives),
        patch("app.bot.get_application", return_value=mock_bot_app),
    ):
        await send_daily_digest()

    mock_get_positives.assert_not_called()
    mock_bot_app.bot.send_message.assert_not_called()


async def test_send_daily_digest_skips_free_users(session_cm_factory) -> None:
    cm, _ = session_cm_factory
    free_user = MagicMock()
    free_user.id = 5
    free_user.plan = "free"
    free_user.sub_status = "active"
    free_user.telegram_user_id = 999

    mock_bot_app = MagicMock()
    mock_bot_app.bot.send_message = AsyncMock()

    with (
        patch("app.services.review_service.AsyncSessionLocal", cm),
        patch("app.repositories.user_repo.get_all_active_subscribers", AsyncMock(return_value=[free_user])),
        patch("app.bot.get_application", return_value=mock_bot_app),
    ):
        await send_daily_digest()

    mock_bot_app.bot.send_message.assert_not_called()
