"""Tests del CLI guardiactl (bin/guardiactl), fase por fase segun capacidad."""
import httpx

from app.cli import guardiactl


class _FakeResponse:
    def __init__(self, status_code, payload):
        self.status_code = status_code
        self._payload = payload

    def raise_for_status(self):
        if self.status_code >= 400:
            raise httpx.HTTPStatusError("error", request=None, response=self)

    def json(self):
        return self._payload

    @property
    def text(self):
        return str(self._payload)


def test_api_error_is_reported_cleanly_not_as_a_traceback(monkeypatch, capsys):
    def fake_get(url, timeout=None):
        return _FakeResponse(502, {"detail": "gce no responde"})

    monkeypatch.setattr(httpx, "get", fake_get)

    rc = guardiactl.main(["vm", "status"])

    assert rc == 1
    assert "gce no responde" in capsys.readouterr().err


def test_connection_error_is_reported_cleanly_not_as_a_traceback(monkeypatch, capsys):
    def fake_get(url, timeout=None):
        raise httpx.ConnectError("connection refused")

    monkeypatch.setattr(httpx, "get", fake_get)

    rc = guardiactl.main(["vm", "status"])

    assert rc == 1
    assert guardiactl.API_URL in capsys.readouterr().err


def test_vm_status_prints_instance_and_status(monkeypatch, capsys):
    def fake_get(url, timeout=None):
        assert url == f"{guardiactl.API_URL}/infra/vm/status"
        return _FakeResponse(200, {"instance": "web-sandbox", "status": "RUNNING"})

    monkeypatch.setattr(httpx, "get", fake_get)

    rc = guardiactl.main(["vm", "status"])

    assert rc == 0
    out = capsys.readouterr().out
    assert "web-sandbox" in out
    assert "RUNNING" in out


def test_vm_start_without_confirm_does_not_call_api(monkeypatch):
    calls = []

    def fake_post(url, json=None, timeout=None):
        calls.append(url)
        return _FakeResponse(202, {})

    monkeypatch.setattr(httpx, "post", fake_post)

    rc = guardiactl.main(["vm", "start"])

    assert rc != 0
    assert calls == []


def test_vm_start_with_confirm_calls_api(monkeypatch):
    def fake_post(url, json=None, timeout=None):
        assert url == f"{guardiactl.API_URL}/infra/vm/start"
        assert json == {"confirm": True}
        return _FakeResponse(202, {"instance": "web-sandbox", "status": "start_requested"})

    monkeypatch.setattr(httpx, "post", fake_post)

    rc = guardiactl.main(["vm", "start", "--confirm"])

    assert rc == 0


def test_dns_get_prints_records(monkeypatch, capsys):
    def fake_get(url, timeout=None):
        assert url == f"{guardiactl.API_URL}/infra/dns"
        return _FakeResponse(
            200,
            {"records": [{"name": "app.example.com", "type": "A", "content": "1.2.3.4"}]},
        )

    monkeypatch.setattr(httpx, "get", fake_get)

    rc = guardiactl.main(["dns", "get"])

    assert rc == 0
    out = capsys.readouterr().out
    assert "app.example.com" in out


def test_dns_restore_without_confirm_does_not_call_api(monkeypatch):
    calls = []

    def fake_post(url, json=None, timeout=None):
        calls.append(url)
        return _FakeResponse(202, {})

    monkeypatch.setattr(httpx, "post", fake_post)

    rc = guardiactl.main(["dns", "restore"])

    assert rc != 0
    assert calls == []


def test_dns_restore_with_confirm_calls_api(monkeypatch):
    def fake_post(url, json=None, timeout=None):
        assert url == f"{guardiactl.API_URL}/infra/dns/restore"
        assert json == {"confirm": True}
        return _FakeResponse(
            202, {"restored": ["app.example.com"], "created": [], "unchanged": []}
        )

    monkeypatch.setattr(httpx, "post", fake_post)

    rc = guardiactl.main(["dns", "restore", "--confirm"])

    assert rc == 0
