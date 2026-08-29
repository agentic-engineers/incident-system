"""Tests del adaptador de Compute Engine (VM web-sandbox, API de guardia)."""
import httpx
import pytest

from app.adapters import gce_adapter


def test_get_instance_status_returns_status_from_api(monkeypatch):
    monkeypatch.setattr(gce_adapter, "get_metadata_token", lambda: "fake-token")

    def fake_get(url, headers=None, timeout=None):
        assert "web-sandbox" in url
        assert headers["Authorization"] == "Bearer fake-token"
        return httpx.Response(200, json={"status": "RUNNING"}, request=httpx.Request("GET", url))

    monkeypatch.setattr(httpx, "get", fake_get)

    assert gce_adapter.get_instance_status() == "RUNNING"


def test_get_instance_status_retries_and_raises_on_persistent_failure(monkeypatch):
    monkeypatch.setattr(gce_adapter, "get_metadata_token", lambda: "fake-token")
    monkeypatch.setattr(gce_adapter.time, "sleep", lambda s: None)
    calls = []

    def fake_get(url, headers=None, timeout=None):
        calls.append(url)
        return httpx.Response(500, json={"error": "boom"}, request=httpx.Request("GET", url))

    monkeypatch.setattr(httpx, "get", fake_get)

    with pytest.raises(gce_adapter.GceError):
        gce_adapter.get_instance_status()
    assert len(calls) == gce_adapter.MAX_RETRIES


def test_instance_name_is_hardcoded_to_the_allowlisted_sandbox():
    assert gce_adapter.INSTANCE_NAME == "web-sandbox"
    assert gce_adapter.INSTANCE_NAME in gce_adapter.ALLOWED_INSTANCES


def test_get_instance_status_rejects_instance_outside_allowlist():
    with pytest.raises(gce_adapter.GceError):
        gce_adapter.get_instance_status(instance="algo-no-permitido")


def test_start_instance_returns_true_on_success(monkeypatch):
    monkeypatch.setattr(gce_adapter, "get_metadata_token", lambda: "fake-token")

    def fake_post(url, headers=None, timeout=None):
        assert url.endswith("/web-sandbox/start")
        assert headers["Authorization"] == "Bearer fake-token"
        return httpx.Response(200, json={}, request=httpx.Request("POST", url))

    monkeypatch.setattr(httpx, "post", fake_post)

    assert gce_adapter.start_instance() is True


def test_start_instance_retries_and_raises_on_persistent_failure(monkeypatch):
    monkeypatch.setattr(gce_adapter, "get_metadata_token", lambda: "fake-token")
    monkeypatch.setattr(gce_adapter.time, "sleep", lambda s: None)
    calls = []

    def fake_post(url, headers=None, timeout=None):
        calls.append(url)
        return httpx.Response(500, json={"error": "boom"}, request=httpx.Request("POST", url))

    monkeypatch.setattr(httpx, "post", fake_post)

    with pytest.raises(gce_adapter.GceError):
        gce_adapter.start_instance()
    assert len(calls) == gce_adapter.MAX_RETRIES


def test_start_instance_rejects_instance_outside_allowlist():
    with pytest.raises(gce_adapter.GceError):
        gce_adapter.start_instance(instance="otra-vm")


def test_get_instance_status_wraps_metadata_token_failure_as_gce_error(monkeypatch):
    def boom_token():
        raise httpx.ConnectError("no route to metadata server")

    monkeypatch.setattr(gce_adapter, "get_metadata_token", boom_token)

    with pytest.raises(gce_adapter.GceError):
        gce_adapter.get_instance_status()


def test_start_instance_wraps_metadata_token_failure_as_gce_error(monkeypatch):
    def boom_token():
        raise httpx.ConnectError("no route to metadata server")

    monkeypatch.setattr(gce_adapter, "get_metadata_token", boom_token)

    with pytest.raises(gce_adapter.GceError):
        gce_adapter.start_instance()
