from app.models import Account, LoopRun, Evaluation, Recommendation, Draft, ContentItem


def test_loop_run_aggregates_children(session):
    acc = Account(platform="x", handle="@a3")
    session.add(acc)
    session.commit()

    run = LoopRun(account_id=acc.id, diagnosis="定位偏散", status="ok", tokens_cost=1234)
    run.evaluation = Evaluation(
        account_id=acc.id,
        composite_score=88.0,
        breakdown={"growth": 90, "engagement": 85, "commercial": 80, "positioning": 95},
    )
    run.recommendations.append(Recommendation(kind="positioning", content="聚焦平价美妆测评", status="pending"))
    run.drafts.append(Draft(kind="topic", content="5款百元粉底横评", review_status="pending"))
    session.add(run)
    session.commit()

    assert run.id is not None
    assert run.evaluation.composite_score == 88.0
    assert run.recommendations[0].status == "pending"
    assert run.drafts[0].review_status == "pending"


def test_content_item_linked_to_account(session):
    acc = Account(platform="tiktok", handle="@a4")
    session.add(acc)
    session.commit()
    ci = ContentItem(account_id=acc.id, platform_post_id="p123", type="video", views=5000, likes=300)
    session.add(ci)
    session.commit()
    assert ci.id is not None
    assert acc.content_items[0].views == 5000
