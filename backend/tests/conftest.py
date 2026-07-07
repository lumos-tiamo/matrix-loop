import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db import Base
import app.models  # noqa: F401  确保所有模型已注册到 Base.metadata


@pytest.fixture()
def session():
    engine = create_engine(
        "sqlite:///:memory:",
        future=True,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    TestSession = sessionmaker(bind=engine, expire_on_commit=False)
    s = TestSession()
    try:
        yield s
    finally:
        s.close()


@pytest.fixture()
def client(session):
    from fastapi.testclient import TestClient
    from app.main import app
    from app.api.deps import get_db

    app.dependency_overrides[get_db] = lambda: session
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()
