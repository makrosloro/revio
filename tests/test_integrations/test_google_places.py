"""Tests for app/integrations/google_places.py — Agent 03."""
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from app.integrations.google_places import GooglePlacesClient


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _mock_http_client(status_code: int, json_body: dict | None = None) -> tuple:
    """Returns (MockClient class, mock http instance) for patching httpx.AsyncClient."""
    mock_response = MagicMock()
    mock_response.status_code = status_code
    mock_response.json.return_value = json_body or {}

    mock_http = AsyncMock()
    mock_http.get = AsyncMock(return_value=mock_response)

    mock_cm = MagicMock()
    mock_cm.__aenter__ = AsyncMock(return_value=mock_http)
    mock_cm.__aexit__ = AsyncMock(return_value=False)

    MockClientClass = MagicMock(return_value=mock_cm)
    return MockClientClass, mock_response


@pytest.fixture
def client() -> GooglePlacesClient:
    return GooglePlacesClient()


# ---------------------------------------------------------------------------
# get_reviews — success paths
# ---------------------------------------------------------------------------

async def test_get_reviews_returns_reviews_on_200(client: GooglePlacesClient) -> None:
    reviews_payload = [
        {"name": "rev_001", "rating": 5, "text": "Genial"},
        {"name": "rev_002", "rating": 2, "text": "Malo"},
    ]
    MockClient, _ = _mock_http_client(200, {"reviews": reviews_payload})

    with patch("app.integrations.google_places.httpx.AsyncClient", MockClient):
        result = await client.get_reviews("ChIJtest")

    assert result == reviews_payload


async def test_get_reviews_returns_empty_when_no_reviews_key(client: GooglePlacesClient) -> None:
    MockClient, _ = _mock_http_client(200, {})

    with patch("app.integrations.google_places.httpx.AsyncClient", MockClient):
        result = await client.get_reviews("ChIJtest")

    assert result == []


# ---------------------------------------------------------------------------
# get_reviews — error paths
# ---------------------------------------------------------------------------

async def test_get_reviews_404_returns_empty(client: GooglePlacesClient) -> None:
    MockClient, _ = _mock_http_client(404)

    with patch("app.integrations.google_places.httpx.AsyncClient", MockClient):
        result = await client.get_reviews("ChIJnotfound")

    assert result == []


async def test_get_reviews_unexpected_status_returns_empty(client: GooglePlacesClient) -> None:
    MockClient, _ = _mock_http_client(500)

    with patch("app.integrations.google_places.httpx.AsyncClient", MockClient):
        result = await client.get_reviews("ChIJerror")

    assert result == []


async def test_get_reviews_rate_limit_retries_then_returns_empty(
    client: GooglePlacesClient,
) -> None:
    """429 on all 3 attempts → empty list, admin alert attempted."""
    MockClient, _ = _mock_http_client(429)

    with (
        patch("app.integrations.google_places.httpx.AsyncClient", MockClient),
        patch("asyncio.sleep", AsyncMock()),
        patch.object(client, "_alert_admin", AsyncMock()) as mock_alert,
    ):
        result = await client.get_reviews("ChIJratelimit")

    assert result == []
    mock_alert.assert_called_once()


async def test_get_reviews_rate_limit_succeeds_on_retry(client: GooglePlacesClient) -> None:
    """429 first, then 200 on second attempt → returns reviews."""
    reviews_payload = [{"name": "rev_001", "rating": 5}]

    response_429 = MagicMock()
    response_429.status_code = 429

    response_200 = MagicMock()
    response_200.status_code = 200
    response_200.json.return_value = {"reviews": reviews_payload}

    mock_http = AsyncMock()
    mock_http.get = AsyncMock(side_effect=[response_429, response_200])

    mock_cm = MagicMock()
    mock_cm.__aenter__ = AsyncMock(return_value=mock_http)
    mock_cm.__aexit__ = AsyncMock(return_value=False)

    with (
        patch("app.integrations.google_places.httpx.AsyncClient", MagicMock(return_value=mock_cm)),
        patch("asyncio.sleep", AsyncMock()),
    ):
        result = await client.get_reviews("ChIJretry")

    assert result == reviews_payload


async def test_get_reviews_network_error_returns_empty(client: GooglePlacesClient) -> None:
    mock_http = AsyncMock()
    mock_http.get = AsyncMock(side_effect=httpx.ConnectError("connection refused"))

    mock_cm = MagicMock()
    mock_cm.__aenter__ = AsyncMock(return_value=mock_http)
    mock_cm.__aexit__ = AsyncMock(return_value=False)

    with (
        patch("app.integrations.google_places.httpx.AsyncClient", MagicMock(return_value=mock_cm)),
        patch("asyncio.sleep", AsyncMock()),
    ):
        result = await client.get_reviews("ChIJnetwork")

    assert result == []
