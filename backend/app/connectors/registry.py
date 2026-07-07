from __future__ import annotations

from app.config import settings as default_settings
from app.connectors.scrapecreators import ScrapeCreatorsConnector
from app.connectors.x import XConnector

SCRAPE_PLATFORMS = {"tiktok", "instagram"}


def resolve_connector(platform: str, cfg=None):
    """Return (connector | None, tier). None connector => manual-only (use CSV import)."""
    cfg = cfg or default_settings
    if platform == "twitter" and cfg.x_bearer_token:
        return XConnector(cfg.x_bearer_token), "api"
    if platform in SCRAPE_PLATFORMS and cfg.scrapecreators_api_key:
        return ScrapeCreatorsConnector(cfg.scrapecreators_api_key, platform), "scrape"
    return None, "manual"
