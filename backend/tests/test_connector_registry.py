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
