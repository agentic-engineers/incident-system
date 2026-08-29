"""Tests de los endpoints de infraestructura de guardia (VM y DNS)."""
import os

os.environ.setdefault("DATABASE_URL", "sqlite:///./test_infra_api.db")

from fastapi.testclient import TestClient

from app.adapters import cloudflare_dns_adapter, gce_adapter
from app.api.main import app

client = TestClient(app)


def test_vm_status_returns_adapter_status(monkeypatch):
    monkeypatch.setattr(gce_adapter, "get_instance_status", lambda: "RUNNING")
    resp = client.get("/infra/vm/status")
    assert resp.status_code == 200
    assert resp.json() == {"instance": "web-sandbox", "status": "RUNNING"}


def test_vm_status_degrades_to_502_on_adapter_error(monkeypatch):
    def boom():
        raise gce_adapter.GceError("gce no responde")

    monkeypatch.setattr(gce_adapter, "get_instance_status", boom)
    resp = client.get("/infra/vm/status")
    assert resp.status_code == 502


def test_vm_start_without_confirm_is_rejected():
    resp = client.post("/infra/vm/start", json={"confirm": False})
    assert resp.status_code == 400


def test_vm_start_missing_confirm_field_defaults_to_rejected():
    resp = client.post("/infra/vm/start", json={})
    assert resp.status_code == 400


def test_vm_start_with_confirm_calls_adapter_and_writes_audit_event(monkeypatch):
    from app.db import SessionLocal
    from app.domain.models import AuditEvent

    monkeypatch.setattr(gce_adapter, "start_instance", lambda: True)

    resp = client.post("/infra/vm/start", json={"confirm": True})

    assert resp.status_code == 202
    assert resp.json() == {"instance": "web-sandbox", "status": "start_requested"}
    with SessionLocal() as s:
        events = s.query(AuditEvent).filter(AuditEvent.action == "vm_start").all()
    assert len(events) >= 1


def test_vm_start_degrades_to_502_on_adapter_error(monkeypatch):
    def boom():
        raise gce_adapter.GceError("fallo al arrancar")

    monkeypatch.setattr(gce_adapter, "start_instance", boom)
    resp = client.post("/infra/vm/start", json={"confirm": True})
    assert resp.status_code == 502


def test_dns_get_returns_records(monkeypatch):
    fake_records = [{"id": "r1", "name": "app.example.com", "type": "A", "content": "1.2.3.4"}]
    monkeypatch.setattr(cloudflare_dns_adapter, "get_dns_records", lambda: fake_records)

    resp = client.get("/infra/dns")

    assert resp.status_code == 200
    assert resp.json() == {"records": fake_records}


def test_dns_get_degrades_to_502_on_adapter_error(monkeypatch):
    def boom():
        raise cloudflare_dns_adapter.CloudflareError("cloudflare no responde")

    monkeypatch.setattr(cloudflare_dns_adapter, "get_dns_records", boom)
    resp = client.get("/infra/dns")
    assert resp.status_code == 502


def test_dns_restore_without_confirm_is_rejected():
    resp = client.post("/infra/dns/restore", json={"confirm": False})
    assert resp.status_code == 400


def test_dns_restore_with_confirm_calls_adapter_and_writes_audit_event(monkeypatch):
    from app.db import SessionLocal
    from app.domain.models import AuditEvent

    fake_summary = {"restored": ["app.example.com"], "created": [], "unchanged": []}
    monkeypatch.setattr(cloudflare_dns_adapter, "restore_dns_records", lambda: fake_summary)

    resp = client.post("/infra/dns/restore", json={"confirm": True})

    assert resp.status_code == 202
    assert resp.json() == fake_summary
    with SessionLocal() as s:
        events = s.query(AuditEvent).filter(AuditEvent.action == "dns_restore").all()
    assert len(events) >= 1


def test_dns_restore_degrades_to_502_on_adapter_error(monkeypatch):
    def boom():
        raise cloudflare_dns_adapter.CloudflareError("fallo al restaurar")

    monkeypatch.setattr(cloudflare_dns_adapter, "restore_dns_records", boom)
    resp = client.post("/infra/dns/restore", json={"confirm": True})
    assert resp.status_code == 502
