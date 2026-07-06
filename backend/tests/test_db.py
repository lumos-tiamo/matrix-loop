from sqlalchemy import text

from app.db import Base, engine, SessionLocal


def test_engine_connects():
    with engine.connect() as conn:
        assert conn.execute(text("SELECT 1")).scalar() == 1


def test_session_and_base_exist():
    assert Base is not None
    session = SessionLocal()
    try:
        assert session.execute(text("SELECT 1")).scalar() == 1
    finally:
        session.close()
