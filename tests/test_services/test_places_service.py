"""Tests for app/services/places_service.py — Agent 03."""
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.places_service import _parse_place_id, extract_place_id_from_url


# ---------------------------------------------------------------------------
# _parse_place_id (synchronous — no mocking needed)
# ---------------------------------------------------------------------------

def test_parse_place_id_from_path_chij() -> None:
    url = "https://www.google.com/maps/place/Restaurante+ABC/ChIJtest1234567890abc/@40.4,-3.7,15z"
    result = _parse_place_id(url)
    assert result == "ChIJtest1234567890abc"


def test_parse_place_id_from_query_param() -> None:
    url = "https://www.google.com/maps/search/?q=place_id:ChIJqparamtest12345"
    result = _parse_place_id(url)
    assert result == "ChIJqparamtest12345"


def test_parse_cid_url_returns_none() -> None:
    url = "https://maps.google.com/?cid=12345678901234"
    result = _parse_place_id(url)
    assert result is None


def test_parse_unrecognized_url_returns_none() -> None:
    url = "https://www.google.com/maps/@40.4,-3.7,15z"
    result = _parse_place_id(url)
    assert result is None


def test_parse_query_param_takes_priority_over_path() -> None:
    url = "https://www.google.com/maps/place/Name/ChIJpath/?q=place_id:ChIJquery12345678"
    result = _parse_place_id(url)
    # query param takes priority
    assert result == "ChIJquery12345678"


def test_parse_place_id_must_be_at_least_20_chars() -> None:
    # 'short' is < 20 chars and doesn't start with ChIJ → should not match
    url = "https://www.google.com/maps/place/Name/shortid/"
    result = _parse_place_id(url)
    assert result is None


# ---------------------------------------------------------------------------
# extract_place_id_from_url (async — tests short URL redirect)
# ---------------------------------------------------------------------------

async def test_extract_place_id_direct_url() -> None:
    url = "https://www.google.com/maps/place/Restaurant/ChIJtest123456789abc/@40.4,-3.7"
    result = await extract_place_id_from_url(url)
    assert result == "ChIJtest123456789abc"


async def test_extract_place_id_short_url_follows_redirect() -> None:
    resolved = "https://www.google.com/maps/place/Bar+Test/ChIJredirect1234567890/@40.4,-3.7"

    mock_response = MagicMock()
    mock_response.url = resolved

    mock_client = AsyncMock()
    mock_client.get = AsyncMock(return_value=mock_response)

    mock_cm = MagicMock()
    mock_cm.__aenter__ = AsyncMock(return_value=mock_client)
    mock_cm.__aexit__ = AsyncMock(return_value=False)

    with patch("app.services.places_service.httpx.AsyncClient", return_value=mock_cm):
        result = await extract_place_id_from_url("https://goo.gl/maps/abc123")

    assert result == "ChIJredirect1234567890"


async def test_extract_place_id_returns_none_on_exception() -> None:
    with patch(
        "app.services.places_service._resolve_url",
        side_effect=Exception("network error"),
    ):
        result = await extract_place_id_from_url("https://goo.gl/maps/fail")

    assert result is None
