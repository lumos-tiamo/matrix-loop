import os

from sqlalchemy import create_engine
from sqlalchemy.engine import make_url
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.config import settings

# Fix #5: ensure parent directory exists for file-based SQLite
url = make_url(settings.database_url)
if url.drivername.startswith("sqlite") and url.database and url.database != ":memory:":
    os.makedirs(os.path.dirname(os.path.abspath(url.database)) or ".", exist_ok=True)

connect_args = {"check_same_thread": False} if settings.database_url.startswith("sqlite") else {}
# Fix #6: removed future=True (no-op in SQLAlchemy 2.0)
engine = create_engine(settings.database_url, connect_args=connect_args)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


class Base(DeclarativeBase):
    pass
