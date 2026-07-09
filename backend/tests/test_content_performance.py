from app.models import Account, ContentItem
from app.analysis.performance import content_performance, performance_prompt_block


def test_content_performance_ranks_winners_losers(session):
    acc = Account(platform="tiktok", handle="@x"); session.add(acc); session.commit()
    session.add_all([
        ContentItem(account_id=acc.id, topic="airdrop guide", views=12000, likes=800),
        ContentItem(account_id=acc.id, topic="meme recap", views=300, likes=10),
        ContentItem(account_id=acc.id, topic="defi yields", views=5000, likes=200),
        ContentItem(account_id=acc.id, topic="no-views draft", views=None),
    ]); session.commit()
    perf = content_performance(session, acc.id)
    assert perf["count"] == 3                                  # None-views excluded
    assert perf["winners"][0]["topic"] == "airdrop guide"
    # with top=3 (default) and only 3 items, winners absorbs all → losers is empty (no overlap)
    assert perf["losers"] == []
    assert perf["median_views"] == 5000


def test_performance_prompt_block_mentions_winners_or_empty(session):
    acc = Account(platform="tiktok", handle="@y"); session.add(acc); session.commit()
    assert performance_prompt_block(content_performance(session, acc.id)) == ""   # no data -> empty
    session.add(ContentItem(account_id=acc.id, topic="airdrop guide", views=9000)); session.commit()
    block = performance_prompt_block(content_performance(session, acc.id))
    assert "airdrop guide" in block and "9000" in block


def test_no_overlap_two_items(session):
    """With exactly 2 items, losers must be empty (winners absorbs all, no overlap)."""
    acc = Account(platform="tiktok", handle="@z"); session.add(acc); session.commit()
    session.add_all([
        ContentItem(account_id=acc.id, topic="top post", views=5000),
        ContentItem(account_id=acc.id, topic="low post", views=100),
    ]); session.commit()
    perf = content_performance(session, acc.id, top=3)
    assert perf["winners"][0]["topic"] == "top post"
    assert perf["losers"] == []   # only 2 items, top=3 consumes all -> losers slice is empty


def test_no_overlap_three_items(session):
    """With 3 items and top=1, no item appears in both winners and losers."""
    acc = Account(platform="tiktok", handle="@w"); session.add(acc); session.commit()
    session.add_all([
        ContentItem(account_id=acc.id, topic="best", views=9000),
        ContentItem(account_id=acc.id, topic="mid", views=4000),
        ContentItem(account_id=acc.id, topic="worst", views=100),
    ]); session.commit()
    perf = content_performance(session, acc.id, top=1)
    winner_topics = {r["topic"] for r in perf["winners"]}
    loser_topics = {r["topic"] for r in perf["losers"]}
    assert winner_topics == {"best"}
    assert loser_topics == {"worst"}
    assert winner_topics.isdisjoint(loser_topics)
