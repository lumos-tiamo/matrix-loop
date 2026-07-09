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
    assert perf["losers"][-1]["topic"] == "meme recap"
    assert perf["median_views"] == 5000


def test_performance_prompt_block_mentions_winners_or_empty(session):
    acc = Account(platform="tiktok", handle="@y"); session.add(acc); session.commit()
    assert performance_prompt_block(content_performance(session, acc.id)) == ""   # no data -> empty
    session.add(ContentItem(account_id=acc.id, topic="airdrop guide", views=9000)); session.commit()
    block = performance_prompt_block(content_performance(session, acc.id))
    assert "airdrop guide" in block and "9000" in block
