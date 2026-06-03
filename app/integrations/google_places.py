import asyncio
import logging

import httpx

from app.config import settings

logger = logging.getLogger(__name__)

_PLACES_BASE = "https://places.googleapis.com/v1/places"
_SEARCH_URL = "https://places.googleapis.com/v1/places:searchText"
_MAX_RETRIES = 3


class GooglePlacesClient:
    def __init__(self) -> None:
        self._api_key = settings.GOOGLE_PLACES_API_KEY

    async def get_reviews(self, place_id: str) -> list[dict]:
        """Fetch reviews in their original language. Returns empty list on unrecoverable error."""
        url = f"{_PLACES_BASE}/{place_id}"
        headers = {
            "X-Goog-Api-Key": self._api_key,
            # originalText preserves the language the review was written in.
            # text.text may be auto-translated by Google.
            "X-Goog-FieldMask": "reviews.rating,reviews.authorAttribution,reviews.publishTime,reviews.text,reviews.originalText",
        }
        for attempt in range(1, _MAX_RETRIES + 1):
            try:
                async with httpx.AsyncClient(timeout=15) as client:
                    response = await client.get(url, headers=headers)

                if response.status_code == 200:
                    data = response.json()
                    return data.get("reviews", [])

                if response.status_code == 429:
                    wait = 2 ** attempt
                    logger.warning(
                        "Google Places rate limit for %s, retry %d/%d in %ds",
                        place_id, attempt, _MAX_RETRIES, wait,
                    )
                    if attempt < _MAX_RETRIES:
                        await asyncio.sleep(wait)
                        continue
                    await self._alert_admin(f"Google Places cuota agotada para place_id={place_id}")
                    return []

                if response.status_code == 404:
                    logger.warning("Place ID not found: %s", place_id)
                    return []

                logger.error(
                    "Google Places unexpected status %d for %s",
                    response.status_code, place_id,
                )
                return []

            except httpx.RequestError:
                logger.exception("Google Places request error for %s (attempt %d)", place_id, attempt)
                if attempt < _MAX_RETRIES:
                    await asyncio.sleep(2 ** attempt)
                    continue
                return []

        return []

    async def search_by_text(self, query: str) -> list[dict]:
        """Search places by free-text query. Returns up to 5 results with id, name, address."""
        headers = {
            "X-Goog-Api-Key": self._api_key,
            "X-Goog-FieldMask": "places.id,places.displayName,places.formattedAddress",
        }
        body = {"textQuery": query, "languageCode": "es", "maxResultCount": 5}
        try:
            async with httpx.AsyncClient(timeout=15) as client:
                response = await client.post(_SEARCH_URL, headers=headers, json=body)

            if response.status_code == 200:
                places = response.json().get("places", [])
                return [
                    {
                        "id": p.get("id", ""),
                        "name": p.get("displayName", {}).get("text", ""),
                        "address": p.get("formattedAddress", ""),
                    }
                    for p in places
                    if p.get("id")
                ]

            logger.error("Places text search failed: HTTP %d", response.status_code)
            return []
        except httpx.RequestError:
            logger.exception("Places text search request error for query: %s", query)
            return []

    async def _alert_admin(self, message: str) -> None:
        from app.bot import get_application

        try:
            app = get_application()
            await app.bot.send_message(chat_id=settings.BOT_ADMIN_CHAT_ID, text=f"⚠️ {message}")
        except Exception:
            logger.exception("Failed to send admin alert: %s", message)
