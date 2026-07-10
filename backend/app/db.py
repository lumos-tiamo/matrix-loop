import os

from sqlalchemy import create_engine, event
from sqlalchemy.engine import make_url
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.config import settings

_IS_SQLITE = settings.database_url.startswith("sqlite")

# Fix #5: ensure parent directory exists for file-based SQLite
url = make_url(settings.database_url)
if url.drivername.startswith("sqlite") and url.database and url.database != ":memory:":
    os.makedirs(os.path.dirname(os.path.abspath(url.database)) or ".", exist_ok=True)

# SQLite concurrency: `timeout` is the busy-timeout (wait for a lock rather than erroring
# immediately). WAL (set per-connection below) lets readers not block the writer — the
# flywheel UI polls /flywheel while autopilot writes. Together with the governor committing
# the "generating" row before the slow provider.generate(), this prevents "database is locked".
connect_args = {"check_same_thread": False, "timeout": 30} if _IS_SQLITE else {}
# Fix #6: removed future=True (no-op in SQLAlchemy 2.0)
engine = create_engine(settings.database_url, connect_args=connect_args)

if _IS_SQLITE:
    @event.listens_for(engine, "connect")
    def _sqlite_pragmas(dbapi_conn, _record):  # pragma: no cover - trivial connection hook
        cur = dbapi_conn.cursor()
        cur.execute("PRAGMA journal_mode=WAL")
        cur.execute("PRAGMA busy_timeout=30000")
        cur.close()

SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


class Base(DeclarativeBase):
    pass
