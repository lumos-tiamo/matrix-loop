from app.config import Settings


def test_new_ingestion_settings_default_none():
    s = Settings()
    assert s.aitoearn_base_url is None
    assert s.aitoearn_api_key is None
    assert s.youtube_api_key is None
    assert s.instagram_token is None
    assert s.instagram_business_id is None


def test_new_ingestion_settings_can_be_set():
    s = Settings(aitoearn_base_url="http://x/api/v2", aitoearn_api_key="k",
                 youtube_api_key="yt", instagram_token="ig", instagram_business_id="123")
    assert s.aitoearn_base_url == "http://x/api/v2"
    assert s.aitoearn_api_key == "k"
    assert s.youtube_api_key == "yt"
    assert s.instagram_token == "ig"
    assert s.instagram_business_id == "123"
