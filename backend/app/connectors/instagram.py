from __future__ import annotations

from app.connectors.base import ConnectorResult


class InstagramConnector:
    """Instagram Graph API business-discovery -> follower snapshot. Injected http_get for tests.

    Reads another business/creator account's public counts via the caller's own IG
    business account id + a long-lived access token.
    """

    tier = "api"

    def __init__(self, access_token: str, business_id: str, http_get=None):
        self.access_token = access_token
        self.business_id = business_id
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
        url = (
            f"https://graph.facebook.com/v19.0/{self.business_id}"
            f"?fields=business_discovery.username({handle}){{followers_count,media_count}}"
            f"&access_token={self.access_token}"
        )
        data = self._http_get(url, {}) or {}
        disc = data.get("business_discovery") or {}
        followers = disc.get("followers_count")
        snapshots = [{"followers": followers}] if followers is not None else []
        return ConnectorResult(tier=self.tier, snapshots=snapshots)
