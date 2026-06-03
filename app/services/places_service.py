import logging
import re

import httpx

logger = logging.getLogger(__name__)

_CID_RE = re.compile(r"[?&]cid=(\d+)")
_PLACE_ID_RE = re.compile(r"[?&]q=place_id:([A-Za-z0-9_-]+)")
_PLACE_PATH_RE = re.compile(r"/place/[^/]+/([A-Za-z0-9_-]{20,})")

_SHORT_URL_HOSTS = {"goo.gl", "maps.app.goo.gl"}


async def extract_place_id_from_url(url: str) -> str | None:
    """Extract a Google Place ID from a Google Maps URL.

    Handles:
    - maps.google.com/?cid=...
    - google.com/maps/place/.../@lat,lng,...
    - goo.gl/maps/... short URLs (follows redirect)
    """
    try:
        resolved_url = await _resolve_url(url)
        return _parse_place_id(resolved_url)
    except Exception:
        logger.exception("Error extracting place_id from url: %s", url)
        return None


async def _resolve_url(url: str) -> str:
    from urllib.parse import urlparse
    parsed = urlparse(url)
    if parsed.netloc in _SHORT_URL_HOSTS:
        async with httpx.AsyncClient(follow_redirects=True, timeout=10) as client:
            response = await client.get(url)
            return str(response.url)
    return url


def _parse_place_id(url: str) -> str | None:
    # Explicit place_id query parameter
    m = _PLACE_ID_RE.search(url)
    if m:
        return m.group(1)

    # Path-based Place ID (ChIJ... style, ≥20 chars)
    m = _PLACE_PATH_RE.search(url)
    if m:
        candidate = m.group(1)
        if candidate.startswith("ChIJ") or len(candidate) >= 20:
            return candidate

    # CID — numeric Google Maps CID (cannot be used directly with Places API v1)
    # Return it prefixed so callers can decide how to handle it
    m = _CID_RE.search(url)
    if m:
        logger.warning("URL contains CID (%s), not a Place ID — manual lookup required", m.group(1))
        return None

    return None
