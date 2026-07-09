from __future__ import annotations

from app.connectors.base import ConnectorResult


def _to_int(v):
    try:
        return int(v)
    except (TypeError, ValueError):
        return None


class YouTubeConnector:
    """YouTube Data API v3 channel statistics -> follower snapshot. Injected http_get for tests."""

    tier = "api"

    def __init__(self, api_key: str, http_get=None):
        self.api_key = api_key
        self._http_get = http_get or self._default_get

    def _default_get(self, url: str, headers: dict) -> dict:
        import httpx
        resp = httpx.get(url, headers=headers or {}, timeout=20)
        resp.raise_for_status()
        return resp.json()

    def fetch(self, account) -> ConnectorResult:
        handle = (account.handle or "").lstrip("@")
        if not handle:
            raise ValueError("account.handle is empty")
        # NOTE: API key/token is in the URL per the API contract — do not log this URL at INFO.
        url = (
            "https://www.googleapis.com/youtube/v3/channels"
            f"?part=statistics&forHandle={handle}&key={self.api_key}"
        )
        data = self._http_get(url, {}) or {}
        items = data.get("items") or []
        if not items:
            return ConnectorResult(tier=self.tier, snapshots=[])
        stats = items[0].get("statistics") or {}
        followers = _to_int(stats.get("subscriberCount"))
        views = _to_int(stats.get("viewCount"))
        snap: dict = {}
        if followers is not None:
            snap["followers"] = followers
        if views is not None:
            snap["views"] = views
        return ConnectorResult(tier=self.tier, snapshots=[snap] if snap else [])
