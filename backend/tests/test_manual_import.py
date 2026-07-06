import io

from app.ingest.manual_import import import_snapshots_csv
from app.models import Account, Snapshot

CSV = """platform,handle,ts,followers,views,engagement_rate,hit_rate,conversions
xiaohongshu,@a1,2026-07-06T00:00:00+00:00,88000,120000,0.043,0.15,3
xiaohongshu,@a1,2026-07-05T00:00:00+00:00,86000,110000,0.041,0.12,2
douyin,@a2,2026-07-06T00:00:00+00:00,120000,900000,0.030,0.05,0
"""


def test_import_creates_accounts_and_snapshots(session):
    result = import_snapshots_csv(session, io.StringIO(CSV))
    assert result["accounts_created"] == 2
    assert result["snapshots_created"] == 3

    accounts = session.query(Account).all()
    assert {a.handle for a in accounts} == {"@a1", "@a2"}

    a1 = session.query(Account).filter_by(handle="@a1").one()
    assert len(a1.snapshots) == 2
    latest = max(a1.snapshots, key=lambda s: s.ts)
    assert latest.followers == 88000
    assert latest.source_tier == "manual"


def test_import_reuses_existing_account(session):
    session.add(Account(platform="xiaohongshu", handle="@a1"))
    session.commit()
    result = import_snapshots_csv(session, io.StringIO(CSV))
    assert result["accounts_created"] == 1  # 只新建了 @a2
    assert session.query(Snapshot).count() == 3
