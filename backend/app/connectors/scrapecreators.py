from __future__ import annotations

from app.connectors.base import ConnectorResult


class ScrapeCreatorsConnector:
    """ScrapeCreators profile lookup for tiktok/instagram -> follower snapshot. Injected http_get for tests."""

    tier = "scrape"

    def __init__(self, api_key: str, platform: str, http_get=None):
        self.api_key = api_key
        self.platform = platform
        self._http_get = http_get or self._default_get

    def _default_get(self, url: str, headers: dict) -> dict:
        import httpx

        resp = httpx.get(url, headers=headers, timeout=20)
        resp.raise_for_status()
        return resp.json()

    def fetch(self, account) -> ConnectorResult:
        handle = account.handle.lstrip("@")
        url = f"https://api.scrapecreators.com/v1/{self.platform}/profile?handle={handle}"
        data = self._http_get(url, {"x-api-key": self.api_key}) or {}
        followers = data.get("followers") if data.get("followers") is not None else data.get("follower_count")
        snapshots = [{"followers": followers}] if followers is not None else []
        return ConnectorResult(tier=self.tier, snapshots=snapshots)
