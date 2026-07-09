from app.connectors.linking import link_aitoearn_accounts
from app.models import Account


class _FakeClient:
    def __init__(self, rows): self._rows = rows
    def list_accounts(self, types=None):
        return {"total": len(self._rows), "list": self._rows}


def test_link_matches_by_platform_and_handle(session):
    acc = Account(platform="xiaohongshu", handle="@nina")
    other = Account(platform="douyin", handle="@zoe")
    session.add_all([acc, other]); session.commit()
    client = _FakeClient([
        {"id": "ae_xhs_1", "type": "xhs", "uid": "u1", "nickname": "nina"},
        {"id": "ae_dy_1", "type": "douyin", "uid": "u2", "nickname": "someone-else"},
    ])
    report = link_aitoearn_accounts(session, client)
    session.refresh(acc); session.refresh(other)
    assert acc.external_ref == "ae_xhs_1" and acc.external_source == "aitoearn"
    assert other.external_ref is None                       # nickname didn't match
    assert report["linked"] == 1 and report["unmatched_accounts"] >= 1


def test_link_matches_by_uid_fallback(session):
    acc = Account(platform="tiktok", handle="@u_abc")
    session.add(acc); session.commit()
    client = _FakeClient([{"id": "ae_tt", "type": "tiktok", "uid": "u_abc", "nickname": "Display Name"}])
    link_aitoearn_accounts(session, client)
    session.refresh(acc)
    assert acc.external_ref == "ae_tt"


def test_set_external_ref_route(client, session):
    acc = Account(platform="xiaohongshu", handle="@x")
    session.add(acc); session.commit()
    resp = client.post(f"/accounts/{acc.id}/external-ref",
                       json={"external_ref": "ae_manual", "external_source": "aitoearn"})
    assert resp.status_code == 200
    session.refresh(acc)
    assert acc.external_ref == "ae_manual"


def test_set_external_ref_404(client):
    assert client.post("/accounts/999/external-ref", json={"external_ref": "x"}).status_code == 404


def test_link_aitoearn_route_reaches_handler_not_shadowed(client):
    # With no AiToEarn config, the handler returns its own 422 ("未配置"),
    # NOT a path-param int-validation 422 for account_id="link-aitoearn".
    resp = client.post("/accounts/link-aitoearn")
    assert resp.status_code == 422
    assert "AiToEarn" in resp.json()["detail"]
