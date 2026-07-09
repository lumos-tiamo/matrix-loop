from app.orchestrator.state import is_paused, set_paused


def test_pause_roundtrip(session):
    assert is_paused(session) is False        # default: not paused
    set_paused(session, True)
    assert is_paused(session) is True
    set_paused(session, False)
    assert is_paused(session) is False
