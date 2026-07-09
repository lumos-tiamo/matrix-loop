def test_ingest_and_list_trends(client, session):
    body = {"trends": [
        {"source": "tiktok", "title": "Airdrop szn is back", "niche": "airdrop", "engagement": 90000,
         "distilled_topic": "3 airdrops to farm this week", "url": "https://t/1"},
        {"source": "youtube", "title": "DeFi yields explained", "niche": "defi", "engagement": 40000},
    ]}
    r = client.post("/trends/ingest", json=body)
    assert r.status_code == 201 and r.json()["ingested"] == 2
    # idempotent: re-post same -> skipped, no dup
    r2 = client.post("/trends/ingest", json=body)
    assert r2.json()["ingested"] == 0 and r2.json()["skipped"] == 2
    rows = client.get("/trends").json()
    assert len(rows) == 2
    airdrop = client.get("/trends?niche=airdrop").json()
    assert len(airdrop) == 1 and airdrop[0]["distilled_topic"] == "3 airdrops to farm this week"


def test_flywheel_crawl_count_reflects_trends(client, session):
    client.post("/trends/ingest", json={"trends": [
        {"source": "tiktok", "title": "t1"}, {"source": "x", "title": "t2"}]})
    fw = client.get("/flywheel").json()
    crawl = next(s for s in fw["steps"] if s["key"] == "crawl")
    assert crawl["count"] == 2 and crawl["status"] == "ok"
