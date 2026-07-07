from __future__ import annotations

from app.connectors.base import ConnectorResult


def _bio_url(user: dict) -> str | None:
    """Prefer the expanded profile URL from entities; fall back to the raw url field.

    Only returns http(s) URLs (skips unresolved shortener/non-URL entity values).
    """
    entities = user.get("entities") or {}
    urls = (entities.get("url") or {}).get("urls") or []
    candidates = [u.get("expanded_url") or u.get("url") for u in urls]
    candidates.append(user.get("url"))
    for c in candidates:
        if c and c.startswith(("http://", "https://")):
            return c
    return None


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
        handle = (account.handle or "").lstrip("@")
        if not handle:
            raise ValueError("account.handle is empty")
        url = (f"https://api.twitter.com/2/users/by/username/{handle}"
               "?user.fields=public_metrics,url,entities")
        data = self._http_get(url, {"Authorization": f"Bearer {self.bearer_token}"})
        user = (data or {}).get("data") or {}
        metrics = user.get("public_metrics") or {}
        followers = metrics.get("followers_count")
        snapshots = [{"followers": followers}] if followers is not None else []
        return ConnectorResult(tier=self.tier, snapshots=snapshots, bio_url=_bio_url(user))
