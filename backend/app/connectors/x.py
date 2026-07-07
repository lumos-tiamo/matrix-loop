from __future__ import annotations

from app.connectors.base import ConnectorResult


class XConnector:
    """X (Twitter) API v2 user lookup -> follower snapshot. Injected http_get for tests."""

    tier = "api"

    def __init__(self, bearer_token: str, http_get=None):
        self.bearer_token = bearer_token
        self._http_get = http_get or self._default_get

    def _default_get(self, url: str, headers: dict) -> dict:
        import httpx

        resp = httpx.get(url, headers=headers, timeout=15)
        resp.raise_for_status()
        return resp.json()

    def fetch(self, account) -> ConnectorResult:
        handle = account.handle.lstrip("@")
        url = f"https://api.twitter.com/2/users/by/username/{handle}?user.fields=public_metrics"
        data = self._http_get(url, {"Authorization": f"Bearer {self.bearer_token}"})
        metrics = ((data or {}).get("data") or {}).get("public_metrics") or {}
        followers = metrics.get("followers_count")
        snapshots = [{"followers": followers}] if followers is not None else []
        return ConnectorResult(tier=self.tier, snapshots=snapshots)
