from __future__ import annotations

from app.config import settings as default_settings
from app.connectors.aitoearn import AiToEarnConnector
from app.connectors.aitoearn_client import AiToEarnClient
from app.connectors.instagram import InstagramConnector
from app.connectors.scrapecreators import ScrapeCreatorsConnector
from app.connectors.x import XConnector
from app.connectors.youtube import YouTubeConnector

# Anti-scraping / browser-login platforms served via a running AiToEarn service.
CN_AGGREGATOR = {"xiaohongshu", "douyin", "weixin_video", "weixin_gzh", "tiktok"}
# Legacy ScrapeCreators fallback (only when nothing better is configured).
SCRAPE_PLATFORMS = {"tiktok", "instagram"}


def resolve_connector(platform: str, cfg=None):
    """Return (connector | None, tier). None connector => manual-only (use CSV import)."""
    cfg = cfg or default_settings
    if platform == "twitter" and cfg.x_bearer_token:
        return XConnector(cfg.x_bearer_token), "api"
    if platform == "youtube" and cfg.youtube_api_key:
        return YouTubeConnector(cfg.youtube_api_key), "api"
    if platform == "instagram" and cfg.instagram_token and cfg.instagram_business_id:
        return InstagramConnector(cfg.instagram_token, cfg.instagram_business_id), "api"
    if platform in CN_AGGREGATOR and cfg.aitoearn_base_url and cfg.aitoearn_api_key:
        client = AiToEarnClient(cfg.aitoearn_base_url, cfg.aitoearn_api_key)
        return AiToEarnConnector(client, platform), "aggregator"
    if platform in SCRAPE_PLATFORMS and cfg.scrapecreators_api_key:
        return ScrapeCreatorsConnector(cfg.scrapecreators_api_key, platform), "scrape"
    return None, "manual"
