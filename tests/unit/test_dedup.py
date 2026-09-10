"""Tests unitarios de deduplicación (camino secuencial)."""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.domain import dedup
from app.domain.models import Base


@pytest.fixture()
def session(tmp_path):
    url = f"sqlite:///{tmp_path}/test.db"
    engine = create_engine(url)
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine)
    s = factory()
    yield s
    s.close()


def test_ingest_creates_incident(session):
    inc = dedup.ingest_incident(session, "monitor", "disco lleno en web-01")
    assert inc.id is not None
    assert inc.status == "new"


def test_ingest_dedups_sequentially(session):
    a = dedup.ingest_incident(session, "monitor", "disco lleno en web-01")
    b = dedup.ingest_incident(session, "monitor", "disco lleno en web-01")
    assert a.id == b.id


def test_different_titles_are_different_incidents(session):
    a = dedup.ingest_incident(session, "monitor", "disco lleno en web-01")
    b = dedup.ingest_incident(session, "monitor", "cpu alta en web-01")
    assert a.id != b.id


def test_ingest_reopens_done_incident(session):
    inc = dedup.ingest_incident(session, "monitor", "disco lleno en web-01")
    assert inc.reopened is False

    inc.status = "done"
    session.commit()

    reopened = dedup.ingest_incident(session, "monitor", "disco lleno en web-01")

    assert reopened.id == inc.id
    assert reopened.status == "new"
    assert reopened.reopened is True
