from app.models import Account, ChannelBrief, Draft, LoopRun


def _seed_account(session, handle="@nina"):
    a = Account(platform="youtube", handle=handle, vertical="crypto")
    session.add(a); session.commit()
    return a


def test_upsert_and_get_brief(client, session):
    acc = _seed_account(session)
    r = client.post(f"/accounts/{acc.id}/brief", json={
        "main_direction": "web3", "sub_niches": ["空投猎人", "DeFi"], "persona": "Nina", "language": "en"})
    assert r.status_code == 200
    body = client.get(f"/accounts/{acc.id}/brief").json()
    assert body["main_direction"] == "web3" and body["sub_niches"] == ["空投猎人", "DeFi"]
    # upsert again updates in place (no duplicate row)
    client.post(f"/accounts/{acc.id}/brief", json={"main_direction": "web3", "tone": "punchy"})
    assert session.query(ChannelBrief).filter_by(account_id=acc.id).count() == 1


def test_get_brief_404_when_absent(client, session):
    acc = _seed_account(session, "@none")
    assert client.get(f"/accounts/{acc.id}/brief").status_code == 404


def test_generate_script_requires_adopted_topic(client, session, monkeypatch):
    acc = _seed_account(session)
    lr = LoopRun(account_id=acc.id); session.add(lr); session.commit()
    topic = Draft(loop_run_id=lr.id, kind="topic", content="Airdrop 101", review_status="pending")
    session.add(topic); session.commit()
    assert client.post(f"/drafts/{topic.id}/generate-script").status_code == 422  # not adopted


def test_generate_script_creates_script_draft(client, session, monkeypatch):
    acc = _seed_account(session)
    session.add(ChannelBrief(account_id=acc.id, main_direction="web3")); session.commit()
    lr = LoopRun(account_id=acc.id); session.add(lr); session.commit()
    topic = Draft(loop_run_id=lr.id, kind="topic", content="Airdrop 101", review_status="adopted")
    session.add(topic); session.commit()

    class _FakeLLM:
        def complete(self, *, system, prompt): return "Hook: airdrops explained ..."
    monkeypatch.setattr("app.api.routes.resolve_llm_client", lambda: _FakeLLM())

    r = client.post(f"/drafts/{topic.id}/generate-script")
    assert r.status_code == 201
    body = r.json()
    assert body["kind"] == "script" and body["review_status"] == "pending"
    assert "airdrops" in body["content"].lower()


def test_generate_script_without_llm_is_422(client, session, monkeypatch):
    acc = _seed_account(session)
    lr = LoopRun(account_id=acc.id); session.add(lr); session.commit()
    topic = Draft(loop_run_id=lr.id, kind="topic", content="X", review_status="adopted")
    session.add(topic); session.commit()
    monkeypatch.setattr("app.api.routes.resolve_llm_client", lambda: None)
    assert client.post(f"/drafts/{topic.id}/generate-script").status_code == 422
