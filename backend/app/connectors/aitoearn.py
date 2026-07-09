from __future__ import annotations

import logging

from app.connectors.base import ConnectorResult, ManualOnlyError

logger = logging.getLogger(__name__)


class AiToEarnConnector:
    """Ingest an account's follower/engagement snapshot from AiToEarn's analytics API.

    Requires account.external_ref (the AiToEarn accountId). Snapshot-level only;
    per-post content ingestion is a separate follow-up plan.
    """

    tier = "aggregator"

    def __init__(self, client, platform: str):
        self.client = client
        self.platform = platform

    def fetch(self, account) -> ConnectorResult:
        external_ref = account.external_ref
        if not external_ref:
            raise ManualOnlyError(
                f"account {account.handle} 未映射 AiToEarn accountId(external_ref);请先 link 或手动设置"
            )
        data = self.client.account_analytics(external_ref) or {}
        metrics = data.get("metrics") or {}
        followers = metrics.get("fansCount")
        views = metrics.get("viewCount")
        engagement = metrics.get("engagementCount")
        snap: dict = {}
        if followers is not None:
            snap["followers"] = followers
        if views is not None:
            snap["views"] = views
        if engagement is not None and views:
            snap["engagement_rate"] = round(engagement / views, 4)
        elif engagement is not None and not views:
            logger.debug("account %s: engagement=%s but views=%s; skipping engagement_rate",
                         getattr(account, "handle", "?"), engagement, views)
        snapshots = [snap] if snap else []
        return ConnectorResult(tier=self.tier, snapshots=snapshots)
