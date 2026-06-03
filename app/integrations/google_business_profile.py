import logging
from datetime import datetime, timedelta, timezone

import httpx

from app.config import settings

logger = logging.getLogger(__name__)

_TOKEN_URL = "https://oauth2.googleapis.com/token"
_ACCOUNTS_URL = "https://mybusinessaccountmanagement.googleapis.com/v1/accounts"
_INFO_BASE = "https://mybusinessbusinessinformation.googleapis.com/v1"
_REVIEWS_BASE = "https://mybusiness.googleapis.com/v4"

# Google returns star rating as an enum string, not an integer
_STAR_MAP = {"ONE": 1, "TWO": 2, "THREE": 3, "FOUR": 4, "FIVE": 5}


class GoogleBusinessProfileClient:
    """Client for reading and replying to reviews via Google Business Profile API."""

    async def refresh_access_token(self, refresh_token: str) -> tuple[str, datetime] | None:
        """Exchange a refresh token for a fresh access token. Returns (token, expires_at)."""
        data = {
            "client_id": settings.GOOGLE_CLIENT_ID,
            "client_secret": settings.GOOGLE_CLIENT_SECRET,
            "refresh_token": refresh_token,
            "grant_type": "refresh_token",
        }
        try:
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.post(_TOKEN_URL, data=data)
            if resp.status_code != 200:
                logger.error("GBP token refresh failed: HTTP %d %s", resp.status_code, resp.text[:200])
                return None
            payload = resp.json()
            access_token = payload["access_token"]
            expires_in = payload.get("expires_in", 3600)
            expires_at = datetime.now(tz=timezone.utc) + timedelta(seconds=expires_in)
            return access_token, expires_at
        except (httpx.RequestError, KeyError):
            logger.exception("Error refreshing GBP access token")
            return None

    async def exchange_code(self, code: str) -> dict | None:
        """Exchange an OAuth authorization code for access + refresh tokens."""
        data = {
            "client_id": settings.GOOGLE_CLIENT_ID,
            "client_secret": settings.GOOGLE_CLIENT_SECRET,
            "code": code,
            "grant_type": "authorization_code",
            "redirect_uri": settings.GOOGLE_REDIRECT_URI,
        }
        try:
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.post(_TOKEN_URL, data=data)
            if resp.status_code != 200:
                logger.error("GBP code exchange failed: HTTP %d %s", resp.status_code, resp.text[:200])
                return None
            return resp.json()
        except httpx.RequestError:
            logger.exception("Error exchanging GBP authorization code")
            return None

    async def list_accounts(self, access_token: str) -> list[dict]:
        """List GBP accounts the user manages. Returns list of {name, accountName}."""
        try:
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.get(
                    _ACCOUNTS_URL, headers={"Authorization": f"Bearer {access_token}"}
                )
            if resp.status_code != 200:
                logger.error("GBP list_accounts failed: HTTP %d %s", resp.status_code, resp.text[:200])
                return []
            return resp.json().get("accounts", [])
        except httpx.RequestError:
            logger.exception("Error listing GBP accounts")
            return []

    async def list_locations(self, access_token: str, account_name: str) -> list[dict]:
        """List locations for a GBP account. Returns list of {name, title, ...}."""
        url = f"{_INFO_BASE}/{account_name}/locations"
        params = {"readMask": "name,title,storefrontAddress", "pageSize": 100}
        try:
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.get(
                    url, headers={"Authorization": f"Bearer {access_token}"}, params=params
                )
            if resp.status_code != 200:
                logger.error("GBP list_locations failed: HTTP %d %s", resp.status_code, resp.text[:200])
                return []
            return resp.json().get("locations", [])
        except httpx.RequestError:
            logger.exception("Error listing GBP locations")
            return []

    async def list_reviews(
        self, access_token: str, account_name: str, location_name: str
    ) -> list[dict]:
        """List ALL reviews for a location (negatives included), normalized.

        location_name format: 'locations/{id}' or 'accounts/{a}/locations/{id}'.
        Returns list of dicts: {review_id, rating, text, author, published_at, reply}.
        """
        # The v4 reviews endpoint needs accounts/{a}/locations/{l}
        loc = location_name
        if loc.startswith("locations/"):
            loc = f"{account_name}/{loc}"
        url = f"{_REVIEWS_BASE}/{loc}/reviews"

        reviews: list[dict] = []
        page_token: str | None = None
        try:
            async with httpx.AsyncClient(timeout=20) as client:
                for _ in range(20):  # safety cap on pagination
                    params = {"pageSize": 50, "orderBy": "updateTime desc"}
                    if page_token:
                        params["pageToken"] = page_token
                    resp = await client.get(
                        url, headers={"Authorization": f"Bearer {access_token}"}, params=params
                    )
                    if resp.status_code != 200:
                        logger.error(
                            "GBP list_reviews failed: HTTP %d %s", resp.status_code, resp.text[:200]
                        )
                        break
                    data = resp.json()
                    for raw in data.get("reviews", []):
                        reviews.append(self._normalize_review(raw, loc))
                    page_token = data.get("nextPageToken")
                    if not page_token:
                        break
        except httpx.RequestError:
            logger.exception("Error listing GBP reviews for %s", loc)

        return reviews

    def _normalize_review(self, raw: dict, location: str) -> dict:
        rating = _STAR_MAP.get(raw.get("starRating", ""), 0)
        reviewer = raw.get("reviewer", {})
        published_raw = raw.get("createTime")
        published_at = None
        if published_raw:
            try:
                published_at = datetime.fromisoformat(published_raw.replace("Z", "+00:00"))
            except ValueError:
                pass
        return {
            # Stable unique id: location + reviewId (GBP reviewId is unique per location)
            "review_id": f"{location}/reviews/{raw.get('reviewId', '')}",
            "rating": rating,
            "text": raw.get("comment"),
            "author": reviewer.get("displayName", "Anónimo"),
            "published_at": published_at,
            "reply": (raw.get("reviewReply") or {}).get("comment"),
        }

    async def reply_to_review(
        self, access_token: str, review_resource: str, reply_text: str
    ) -> bool:
        """Publish a reply to a review. review_resource is the full v4 review name.

        Endpoint: PUT {review_resource}/reply  with body {comment}.
        """
        url = f"{_REVIEWS_BASE}/{review_resource}/reply"
        try:
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.put(
                    url,
                    headers={"Authorization": f"Bearer {access_token}"},
                    json={"comment": reply_text},
                )
            if resp.status_code == 200:
                return True
            logger.error("GBP reply failed: HTTP %d %s", resp.status_code, resp.text[:200])
            return False
        except httpx.RequestError:
            logger.exception("Error replying to GBP review")
            return False
