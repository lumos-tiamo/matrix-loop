from __future__ import annotations

# matrix-loop platform string -> AiToEarn AccountType
PLATFORM_MAP = {
    "xiaohongshu": "xhs",
    "weixin_video": "wxSph",
    "weixin_gzh": "wxGzh",
    "douyin": "douyin",
    "tiktok": "tiktok",
    "twitter": "twitter",
    "youtube": "youtube",
    "instagram": "instagram",
    "bilibili": "bilibili",
}


def to_aitoearn_platform(platform: str) -> str:
    return PLATFORM_MAP.get(platform, platform)


class AiToEarnClient:
    """Thin HTTP client for AiToEarn's REST API. Injected http_get/http_post for tests."""

    def __init__(self, base_url: str, api_key: str, http_get=None, http_post=None):
        self.base_url = (base_url or "").rstrip("/")
        self.api_key = api_key
        self._http_get = http_get or self._default_get
        self._http_post = http_post or self._default_post

    def _headers(self) -> dict:
        return {"x-api-key": self.api_key, "Content-Type": "application/json"}

    def _default_get(self, url: str, headers: dict) -> dict:
        import httpx
        resp = httpx.get(url, headers=headers, timeout=20)
        resp.raise_for_status()
        return resp.json()

    def _default_post(self, url: str, headers: dict, json: dict) -> dict:
        import httpx
        resp = httpx.post(url, headers=headers, json=json, timeout=30)
        resp.raise_for_status()
        return resp.json()

    def list_accounts(self, types: list[str] | None = None) -> dict:
        url = f"{self.base_url}/channels/accounts"
        if types:
            url += "?" + "&".join(f"types[]={t}" for t in types)
        return self._http_get(url, self._headers()) or {}

    def account_analytics(self, account_id: str, since: str | None = None, until: str | None = None) -> dict:
        url = f"{self.base_url}/channels/accounts/{account_id}/analytics"
        qs = [f"{k}={v}" for k, v in (("since", since), ("until", until)) if v]
        if qs:
            url += "?" + "&".join(qs)
        return self._http_get(url, self._headers()) or {}

    def work_analytics(self, platform: str, work_id: str, account_id: str,
                       since: str | None = None, until: str | None = None) -> dict:
        url = f"{self.base_url}/channels/works/{platform}/{work_id}/analytics?accountId={account_id}"
        for k, v in (("since", since), ("until", until)):
            if v:
                url += f"&{k}={v}"
        return self._http_get(url, self._headers()) or {}
