from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.analysis.performance import content_performance, performance_prompt_block
from app.analysis.script import generate_script
from app.analysis.trends import trend_prompt_block
from app.connectors.base import ManualOnlyError
from app.connectors.sync import sync_account
from app.loop.engine import run_loop
from app.models import Account, ChannelBrief, Draft
from app.orchestrator.state import is_paused
from app.publish.dispatch import PublishNotReady, create_dispatch
from app.video.base import NearDuplicateScript, VideoQuotaExceeded
from app.video.governor import generate_video

logger = logging.getLogger(__name__)

STEPS = ["sync", "evaluate", "topic", "script", "video", "approve", "publish", "track"]


@dataclass(frozen=True)
class OrchestratorConfig:
    allow_fake_publish: bool = False           # never publish a fake-provider video as real
    stop_after_consecutive_errors: int = 5
    max_accounts: int | None = None            # cap accounts processed per cycle (None = unlimited)


def _event(session, account_id, cycle_id, step, status, detail=""):
    from app.models import FlywheelEvent
    session.add(FlywheelEvent(account_id=account_id, cycle_id=cycle_id, step=step,
                              status=status, detail=(detail or "")[:400]))


def advance_account(session: Session, account, *, llm=None, video=None, aitoearn=None,
                    sync: bool = True, cfg: OrchestratorConfig | None = None,
                    cycle_id: str | None = None) -> dict:
    """Advance one account through the flywheel. Autopilot accounts auto-advance the human gates
    under guardrails; others stop after producing topic drafts. Degrades gracefully when a
    dependency is missing. Returns {account_id, reached_step, actions, errors}."""
    cfg = cfg or OrchestratorConfig()
    actions: list[str] = []
    reached = "sync"

    def mark(step, status, detail=""):
        nonlocal reached
        _event(session, account.id, cycle_id, step, status, detail)
        if status == "ok":
            reached = step
        actions.append(f"{step}:{status}")

    # ① sync (best-effort)
    if sync:
        try:
            sync_account(session, account)
            mark("sync", "ok")
        except ManualOnlyError:
            mark("sync", "skipped", "manual-only platform / not mapped")
        except Exception as exc:  # noqa: BLE001
            mark("sync", "error", str(exc))

    # ② evaluate + topics (run_loop)
    try:
        run = run_loop(session, account, llm_client=llm)
        mark("evaluate", "ok", f"score={run.evaluation.composite_score if run.evaluation else '?'}")
    except Exception as exc:  # noqa: BLE001
        mark("evaluate", "error", str(exc))
        return {"account_id": account.id, "reached_step": reached, "actions": actions, "errors": [str(exc)]}

    # newest topic draft from this run
    topic = next((d for d in reversed(run.drafts) if d.kind == "topic"), None)
    if topic is not None:
        mark("topic", "ok", topic.content[:60])
    else:
        mark("topic", "skipped", "no topic produced")

    # non-autopilot: stop here (review queue)
    if not account.autopilot:
        session.commit()
        return {"account_id": account.id, "reached_step": reached, "actions": actions, "errors": []}

    # ---- autopilot auto-advance ----
    if topic is None:
        session.commit()
        return {"account_id": account.id, "reached_step": reached, "actions": actions, "errors": []}

    # ③ script — do NOT adopt the topic until the script is successfully generated
    if llm is None:
        mark("script", "blocked", "no LLM configured")
        session.commit()
        return {"account_id": account.id, "reached_step": reached, "actions": actions, "errors": []}
    brief = session.scalar(select(ChannelBrief).where(ChannelBrief.account_id == account.id))
    perf = performance_prompt_block(content_performance(session, account.id))
    trends = trend_prompt_block(session, brief.sub_niches) if brief else ""
    try:
        text = generate_script(topic.content, brief, llm, performance=perf or None, trends=trends or None)
    except Exception as exc:  # noqa: BLE001
        mark("script", "error", str(exc)); session.commit()
        return {"account_id": account.id, "reached_step": reached, "actions": actions, "errors": [str(exc)]}
    topic.review_status = "adopted"          # script succeeded -> now consume the topic
    script = Draft(loop_run_id=topic.loop_run_id, kind="script", content=text, review_status="adopted")
    session.add(script); session.commit()
    mark("script", "ok")

    # ④ video (governed). `video` may be a provider or a per-account resolver
    # callable(account)->provider (lets one cycle route Aurea→avatar, X/IG→other).
    provider = video(account) if callable(video) else video
    if provider is None:
        mark("video", "blocked", "no video provider"); session.commit()
        return {"account_id": account.id, "reached_step": reached, "actions": actions, "errors": []}
    try:
        asset = generate_video(session, account, script, provider=provider)
    except (VideoQuotaExceeded, NearDuplicateScript) as exc:
        mark("video", "blocked", str(exc)); session.commit()
        return {"account_id": account.id, "reached_step": reached, "actions": actions, "errors": []}
    except Exception as exc:  # noqa: BLE001
        mark("video", "error", str(exc)); session.commit()
        return {"account_id": account.id, "reached_step": reached, "actions": actions, "errors": [str(exc)]}
    mark("video", "ok", asset.provider)

    # guardrail: do not publish a fake video as real
    if asset.provider == "fake" and not cfg.allow_fake_publish:
        mark("publish", "blocked", "fake video not published (allow_fake_publish=False)")
        session.commit()
        return {"account_id": account.id, "reached_step": reached, "actions": actions, "errors": []}

    # ⑤ approve (autopilot)
    asset.review_status = "approved"; session.commit()
    mark("approve", "ok")

    # ⑥ publish
    if aitoearn is None or not account.external_ref:
        mark("publish", "blocked", "AiToEarn not configured or account not mapped")
        session.commit()
        return {"account_id": account.id, "reached_step": reached, "actions": actions, "errors": []}
    try:
        create_dispatch(session, account, asset, client=aitoearn, caption=(topic.content or "")[:120])
        mark("publish", "ok")
    except PublishNotReady as exc:
        mark("publish", "blocked", str(exc))
    except Exception as exc:  # noqa: BLE001
        mark("publish", "error", str(exc))

    session.commit()
    return {"account_id": account.id, "reached_step": reached, "actions": actions, "errors": []}


def run_autopilot_cycle(session: Session, *, llm=None, video=None, aitoearn=None,
                        sync: bool = True, cfg: OrchestratorConfig | None = None) -> dict:
    """One scheduled pass: advance every account (autopilot ones through publish; others to review).
    Honors the global pause, isolates per-account failures, and trips a consecutive-error breaker."""
    cfg = cfg or OrchestratorConfig()
    if is_paused(session):
        return {"paused": True, "processed": 0, "results": [], "errors": []}
    cycle_id = uuid.uuid4().hex[:12]
    stmt = select(Account).order_by(Account.id)
    if cfg.max_accounts is not None:
        stmt = stmt.limit(cfg.max_accounts)
    accounts = list(session.scalars(stmt).all())
    processed = 0
    results = []
    errors = []
    consecutive = 0
    for acc in accounts:
        try:
            rep = advance_account(session, acc, llm=llm, video=video, aitoearn=aitoearn,
                                  sync=sync, cfg=cfg, cycle_id=cycle_id)
            results.append(rep)
            processed += 1
            consecutive = 0
        except Exception as exc:  # noqa: BLE001
            logger.warning("cycle: account %s failed: %s", acc.id, exc)
            errors.append({"account_id": acc.id, "error": str(exc)})
            consecutive += 1
            if consecutive >= cfg.stop_after_consecutive_errors:
                break
    return {"paused": False, "cycle_id": cycle_id, "processed": processed,
            "results": results, "errors": errors}
