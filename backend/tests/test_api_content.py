from app.models import Account, ContentItem


def _seed(session):
    a1 = Account(platform="xiaohongshu", handle="@a1")
    a2 = Account(platform="twitter", handle="@a2")
    session.add_all([a1, a2]); session.commit()
    session.add_all([
        ContentItem(account_id=a1.id, topic="beauty", views=5000, likes=400),
        ContentItem(account_id=a1.id, topic="skincare", views=1200, likes=90),
        ContentItem(account_id=a2.id, topic="macro", views=8000, likes=600),
    ])
    session.commit()
    return a1, a2


def test_content_lists_sorted_by_views_with_account(client, session):
    a1, a2 = _seed(session)
    items = client.get("/content").json()
    assert [i["views"] for i in items] == [8000, 5000, 1200]     # views desc
    top = items[0]
    assert top["account_handle"] == "@a2"
    assert top["platform"] == "twitter"


def test_content_filter_by_platform(client, session):
    _seed(session)
    items = client.get("/content?platform=xiaohongshu").json()
    assert len(items) == 2
    assert all(i["platform"] == "xiaohongshu" for i in items)
