from app.models import Trend


def test_trend_persist_defaults(session):
    t = Trend(source="tiktok", title="Airdrop farming blew up", niche="airdrop",
              engagement=120000, distilled_topic="How to farm the next big airdrop")
    session.add(t); session.commit()
    got = session.query(Trend).one()
    assert got.source == "tiktok" and got.niche == "airdrop"
    assert got.score == 0.0 and got.url is None and got.captured_at is not None
