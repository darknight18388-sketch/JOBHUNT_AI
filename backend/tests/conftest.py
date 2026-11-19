import os

import tempfile
from pathlib import Path

os.environ["DATABASE_URL"] = "sqlite://"  # tests never touch PostgreSQL
for _k in ("ADZUNA_APP_ID", "ADZUNA_APP_KEY", "JOOBLE_API_KEY"):
    os.environ[_k] = ""
os.environ["ENABLE_ARBEITNOW"] = "false"
os.environ["UPLOAD_DIR"] = tempfile.mkdtemp(prefix="jobhunt_test_uploads_")

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import app.models  # noqa: F401
from app.database.session import Base, get_db
from app.main import app


@pytest.fixture(autouse=True)
def no_real_feeds(monkeypatch):
    """Tests never read the real sources.json feeds or hit the network."""
    from app.services.connectors.rss import RssConnector
    monkeypatch.setattr(RssConnector, "feeds", lambda self: [])


@pytest.fixture()
def client():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False},
                           poolclass=StaticPool)
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)

    def override():
        db = Session()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override
    yield TestClient(app)
    app.dependency_overrides.clear()
    for f in Path(os.environ["UPLOAD_DIR"]).glob("*"):
        f.unlink()
