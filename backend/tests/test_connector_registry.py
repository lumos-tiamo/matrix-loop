from app.config import Settings
from app.connectors.registry import resolve_connector
from app.connectors.x import XConnector
from app.connectors.scrapecreators import ScrapeCreatorsConnector


def test_twitter_with_token_resolves_api():
    cfg = Settings(x_bearer_token="tok")
    conn, tier = resolve_connector("twitter", cfg)
    assert isinstance(conn, XConnector)
    assert tier == "api"


def test_twitter_without_token_is_manual():
    cfg = Settings(x_bearer_token=None)
    conn, tier = resolve_connector("twitter", cfg)
    assert conn is None
    assert tier == "manual"


def test_tiktok_with_key_resolves_scrape():
    cfg = Settings(scrapecreators_api_key="k")
    conn, tier = resolve_connector("tiktok", cfg)
    assert isinstance(conn, ScrapeCreatorsConnector)
    assert tier == "scrape"


def test_xiaohongshu_is_manual():
    conn, tier = resolve_connector("xiaohongshu", Settings())
    assert conn is None
    assert tier == "manual"


def test_youtube_with_key_resolves_api():
    from app.config import Settings
    from app.connectors.youtube import YouTubeConnector
    conn, tier = resolve_connector("youtube", Settings(youtube_api_key="k"))
    assert isinstance(conn, YouTubeConnector) and tier == "api"


def test_instagram_with_token_resolves_api():
    from app.config import Settings
    from app.connectors.instagram import InstagramConnector
    conn, tier = resolve_connector("instagram", Settings(instagram_token="t", instagram_business_id="b"))
    assert isinstance(conn, InstagramConnector) and tier == "api"


def test_cn_platform_with_aitoearn_resolves_aggregator():
    from app.config import Settings
    from app.connectors.aitoearn import AiToEarnConnector
    cfg = Settings(aitoearn_base_url="http://x/api/v2", aitoearn_api_key="k")
    for platform in ("xiaohongshu", "douyin", "weixin_video", "weixin_gzh", "tiktok"):
        conn, tier = resolve_connector(platform, cfg)
        assert isinstance(conn, AiToEarnConnector) and tier == "aggregator", platform


def test_cn_platform_without_aitoearn_is_manual():
    from app.config import Settings
    conn, tier = resolve_connector("xiaohongshu", Settings())
    assert conn is None and tier == "manual"


def test_tiktok_prefers_aitoearn_over_scrapecreators():
    from app.config import Settings
    from app.connectors.aitoearn import AiToEarnConnector
    cfg = Settings(aitoearn_base_url="http://x/api/v2", aitoearn_api_key="k", scrapecreators_api_key="s")
    conn, tier = resolve_connector("tiktok", cfg)
    assert isinstance(conn, AiToEarnConnector) and tier == "aggregator"
