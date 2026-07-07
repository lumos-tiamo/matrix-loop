from __future__ import annotations


def match_endpoint(url: str, endpoints):
    """Return the first endpoint whose url_pattern is a substring of url, else None."""
    u = (url or "").lower()
    for ep in endpoints:
        pat = (ep.url_pattern or "").lower()
        if pat and pat in u:
            return ep
    return None
