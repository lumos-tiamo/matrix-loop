from __future__ import annotations

import logging
from collections.abc import Callable

from apscheduler.schedulers.background import BackgroundScheduler

from app.config import settings

logger = logging.getLogger(__name__)


def _run_autopilot(session_factory: Callable) -> None:
    from app.orchestrator.engine import run_autopilot_cycle, OrchestratorConfig
    from app.analysis.factory import resolve_llm_client
    from app.video.factory import resolve_video_provider
    from app.config import settings as cfg
    session = session_factory()
    try:
        aitoearn = None
        if cfg.aitoearn_base_url and cfg.aitoearn_api_key:
            from app.connectors.aitoearn_client import AiToEarnClient
            aitoearn = AiToEarnClient(cfg.aitoearn_base_url, cfg.aitoearn_api_key)
        orchestrator_cfg = OrchestratorConfig(
            allow_fake_publish=cfg.orchestrator_allow_fake_publish,
            max_accounts=cfg.schedule_max_accounts,
        )
        rep = run_autopilot_cycle(session, llm=resolve_llm_client(),
                                  video=resolve_video_provider(), aitoearn=aitoearn, sync=True,
                                  cfg=orchestrator_cfg)
        logger.info("autopilot cycle: paused=%s processed=%s errors=%s",
                    rep.get("paused"), rep.get("processed"), len(rep.get("errors", [])))
        if aitoearn is not None:
            from app.publish.analytics import refresh_published_analytics
            refresh_published_analytics(session, client=aitoearn)
    except Exception:
        logger.exception("autopilot cycle failed")
    finally:
        session.close()


def build_scheduler(session_factory: Callable, interval_minutes: int | None = None,
                    max_accounts: int | None = None) -> BackgroundScheduler:
    """Build (but do not start) a scheduler that runs the autopilot cycle every interval_minutes.
    Call .start() on the returned scheduler to begin unattended operation."""
    from app.config import settings as _s
    interval = interval_minutes if interval_minutes is not None else _s.orchestrator_interval_minutes
    scheduler = BackgroundScheduler()
    scheduler.add_job(_run_autopilot, "interval", minutes=interval,
                      args=[session_factory], id="matrixloop-autopilot", replace_existing=True)
    return scheduler
