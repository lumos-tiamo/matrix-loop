from app.models import ContentItem
from app.analysis.content import hit_content, tag_entropy, positioning_proxy_score


def _ci(views, topic=None):
    return ContentItem(account_id=1, views=views, topic=topic)


def test_hit_content_picks_outliers():
    items = [_ci(100), _ci(120), _ci(90), _ci(1000)]  # median ~110, 3x=330
    hits = hit_content(items, multiplier=3.0)
    assert [c.views for c in hits] == [1000]


def test_hit_content_empty():
    assert hit_content([], multiplier=3.0) == []


def test_tag_entropy_single_tag_is_zero():
    items = [_ci(100, "beauty"), _ci(100, "beauty"), _ci(100, "beauty")]
    assert tag_entropy(items) == 0.0


def test_tag_entropy_uniform_is_one():
    items = [_ci(100, "beauty"), _ci(100, "fashion"), _ci(100, "travel"), _ci(100, "food")]
    assert tag_entropy(items) == 1.0


def test_tag_entropy_no_tags_is_zero():
    assert tag_entropy([_ci(100), _ci(100)]) == 0.0


def test_positioning_proxy_focused_is_high():
    focused = [_ci(100, "beauty")] * 4
    scattered = [_ci(100, "beauty"), _ci(100, "fashion"), _ci(100, "travel"), _ci(100, "food")]
    assert positioning_proxy_score(focused) == 100.0
    assert positioning_proxy_score(scattered) == 0.0
