"""Tests de la API (sobre sqlite, sin red)."""
import os

os.environ.setdefault("DATABASE_URL", "sqlite:///./test_api.db")

from fastapi.testclient import TestClient

from app.api.main import app
from app.db import SessionLocal
from app.domain import dedup

client = TestClient(app)


def test_health():
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


def test_version_has_commit_field():
    resp = client.get("/version")
    assert resp.status_code == 200
    assert "commit" in resp.json()


def test_create_and_list_incident():
    resp = client.post(
        "/incidents",
        json={"source": "api-test", "title": "algo se cayo", "body": "detalle"},
    )
    assert resp.status_code == 200
    created = resp.json()
    assert created["status"] == "new"

    resp = client.get("/incidents")
    assert resp.status_code == 200
    listed = next(i for i in resp.json() if i["id"] == created["id"])
    assert listed["reopened"] is False


def test_list_incident_marks_reopened_after_done_to_new_cycle():
    session = SessionLocal()
    try:
        inc = dedup.ingest_incident(session, "api-test", "algo se reabre", "detalle")
        inc.status = "done"
        session.commit()
        dedup.ingest_incident(session, "api-test", "algo se reabre", "detalle")
    finally:
        session.close()

    resp = client.get("/incidents")
    assert resp.status_code == 200
    listed = next(i for i in resp.json() if i["id"] == inc.id)
    assert listed["status"] == "new"
    assert listed["reopened"] is True
