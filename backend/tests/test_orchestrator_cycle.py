import json
from datetime import datetime, timezone

from app.models import Account, Snapshot
from app.orchestrator.engine import run_autopilot_cycle, OrchestratorConfig
from app.orchestrator.state import set_paused

_ANALYSIS_JSON = json.dumps({
    "positioning_clarity": 70,
    "positioning_label": "crypto",
    "content_direction": "focus on alpha",
    "suggested_topics": ["airdrop guide"],
})


class _LLM2:
    def complete(self, *, system, prompt): return _ANALYSIS_JSON
    last_usage = {"input": 1, "output": 1}


def _acct(session, handle, autopilot):
    a = Account(platform="tiktok", handle=handle, autopilot=autopilot, external_ref="ae",
                objective_weights={"growth": 1.0, "engagement": 0.0, "commercial": 0.0, "positioning": 0.0})
    session.add(a); session.commit()
    session.add(Snapshot(account_id=a.id, ts=datetime(2026, 7, 1, tzinfo=timezone.utc), followers=100))
    session.commit()
    return a


def test_cycle_processes_all_accounts(session):
    _acct(session, "@a", True); _acct(session, "@b", False)
    rep = run_autopilot_cycle(session, llm=_LLM2(), video=None, aitoearn=None, sync=False)
    assert rep["processed"] == 2
    assert rep["paused"] is False


def test_cycle_respects_global_pause(session):
    _acct(session, "@a", True)
    set_paused(session, True)
    rep = run_autopilot_cycle(session, llm=_LLM2(), video=None, aitoearn=None, sync=False)
    assert rep["paused"] is True and rep["processed"] == 0
