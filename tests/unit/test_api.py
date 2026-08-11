"""Tests de la API (sobre sqlite, sin red)."""
import os

os.environ.setdefault("DATABASE_URL", "sqlite:///./test_api.db")

from fastapi.testclient import TestClient

from app.api.main import app

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
    assert any(i["id"] == created["id"] for i in resp.json())


def test_list_incidents_filtered_by_status():
    created = client.post(
        "/incidents",
        json={"source": "api-test", "title": "filtro por status", "body": "detalle"},
    ).json()

    resp = client.get("/incidents", params={"status": "new"})
    assert resp.status_code == 200
    assert any(i["id"] == created["id"] for i in resp.json())

    resp = client.get("/incidents", params={"status": "done"})
    assert resp.status_code == 200
    assert all(i["id"] != created["id"] for i in resp.json())
