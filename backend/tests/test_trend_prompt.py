from app.models import Trend
from app.analysis.trends import trend_prompt_block


def test_trend_block_empty(session):
    assert trend_prompt_block(session) == ""


def test_trend_block_lists_recent(session):
    session.add_all([
        Trend(source="tiktok", title="Airdrop szn", niche="airdrop", distilled_topic="Farm 3 airdrops now"),
        Trend(source="x", title="Meme rotation", niche="meme", distilled_topic="Why memes pump Fridays"),
    ]); session.commit()
    block = trend_prompt_block(session)
    assert "Farm 3 airdrops now" in block or "Airdrop szn" in block
    # niche filter
    b2 = trend_prompt_block(session, niches=["airdrop"])
    assert "airdrop" in b2.lower() and "meme rotation" not in b2.lower()
