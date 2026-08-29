"""Tests del adaptador de DNS via Cloudflare (API de guardia)."""
import httpx
import pytest

from app.adapters import cloudflare_dns_adapter


def test_get_dns_records_returns_list_from_api(monkeypatch):
    monkeypatch.setattr(cloudflare_dns_adapter, "CF_API_TOKEN", "fake-token")
    monkeypatch.setattr(cloudflare_dns_adapter, "CF_ZONE_ID", "zone123")

    def fake_get(url, headers=None, timeout=None):
        assert "zone123" in url
        assert headers["Authorization"] == "Bearer fake-token"
        return httpx.Response(
            200,
            json={
                "result": [
                    {"id": "r1", "name": "app.example.com", "type": "A", "content": "1.2.3.4"}
                ]
            },
            request=httpx.Request("GET", url),
        )

    monkeypatch.setattr(httpx, "get", fake_get)

    records = cloudflare_dns_adapter.get_dns_records()
    assert records == [
        {"id": "r1", "name": "app.example.com", "type": "A", "content": "1.2.3.4"}
    ]


def test_get_dns_records_retries_and_raises_on_persistent_failure(monkeypatch):
    monkeypatch.setattr(cloudflare_dns_adapter, "CF_API_TOKEN", "fake-token")
    monkeypatch.setattr(cloudflare_dns_adapter, "CF_ZONE_ID", "zone123")
    monkeypatch.setattr(cloudflare_dns_adapter.time, "sleep", lambda s: None)
    calls = []

    def fake_get(url, headers=None, timeout=None):
        calls.append(url)
        return httpx.Response(500, json={"errors": ["boom"]}, request=httpx.Request("GET", url))

    monkeypatch.setattr(httpx, "get", fake_get)

    with pytest.raises(cloudflare_dns_adapter.CloudflareError):
        cloudflare_dns_adapter.get_dns_records()
    assert len(calls) == cloudflare_dns_adapter.MAX_RETRIES


def test_no_delete_capability_exists_in_module():
    assert not hasattr(cloudflare_dns_adapter, "delete_dns_record")


def test_restore_updates_drifted_record_and_creates_missing_one(monkeypatch):
    monkeypatch.setattr(
        cloudflare_dns_adapter,
        "KNOWN_GOOD_RECORDS",
        [
            {"name": "app.example.com", "type": "A", "content": "1.2.3.4"},
            {"name": "api.example.com", "type": "A", "content": "5.6.7.8"},
        ],
    )
    monkeypatch.setattr(
        cloudflare_dns_adapter,
        "get_dns_records",
        lambda: [
            {"id": "r1", "name": "app.example.com", "type": "A", "content": "9.9.9.9"},
            {"id": "r2", "name": "unrelated.example.com", "type": "A", "content": "0.0.0.0"},
        ],
    )

    put_calls = []
    post_calls = []

    def fake_put(url, headers=None, json=None, timeout=None):
        put_calls.append((url, json))
        return httpx.Response(200, json={"success": True}, request=httpx.Request("PUT", url))

    def fake_post(url, headers=None, json=None, timeout=None):
        post_calls.append((url, json))
        return httpx.Response(200, json={"success": True}, request=httpx.Request("POST", url))

    monkeypatch.setattr(httpx, "put", fake_put)
    monkeypatch.setattr(httpx, "post", fake_post)

    summary = cloudflare_dns_adapter.restore_dns_records()

    assert summary == {
        "restored": ["app.example.com"],
        "created": ["api.example.com"],
        "unchanged": [],
    }
    assert len(put_calls) == 1
    assert put_calls[0][0].endswith("/dns_records/r1")
    assert put_calls[0][1]["content"] == "1.2.3.4"
    assert len(post_calls) == 1
    assert post_calls[0][1]["name"] == "api.example.com"


def test_restore_leaves_unlisted_records_untouched(monkeypatch):
    monkeypatch.setattr(
        cloudflare_dns_adapter,
        "KNOWN_GOOD_RECORDS",
        [{"name": "app.example.com", "type": "A", "content": "1.2.3.4"}],
    )
    monkeypatch.setattr(
        cloudflare_dns_adapter,
        "get_dns_records",
        lambda: [
            {"id": "r1", "name": "app.example.com", "type": "A", "content": "1.2.3.4"},
            {"id": "r2", "name": "unrelated.example.com", "type": "A", "content": "0.0.0.0"},
        ],
    )
    calls = []
    monkeypatch.setattr(httpx, "put", lambda *a, **k: calls.append("put"))
    monkeypatch.setattr(httpx, "post", lambda *a, **k: calls.append("post"))

    summary = cloudflare_dns_adapter.restore_dns_records()

    assert summary == {"restored": [], "created": [], "unchanged": ["app.example.com"]}
    assert calls == []


def test_restore_raises_when_update_fails_persistently(monkeypatch):
    monkeypatch.setattr(
        cloudflare_dns_adapter,
        "KNOWN_GOOD_RECORDS",
        [{"name": "app.example.com", "type": "A", "content": "1.2.3.4"}],
    )
    monkeypatch.setattr(
        cloudflare_dns_adapter,
        "get_dns_records",
        lambda: [{"id": "r1", "name": "app.example.com", "type": "A", "content": "9.9.9.9"}],
    )
    monkeypatch.setattr(cloudflare_dns_adapter.time, "sleep", lambda s: None)

    def fake_put(url, headers=None, json=None, timeout=None):
        return httpx.Response(500, json={"errors": ["boom"]}, request=httpx.Request("PUT", url))

    monkeypatch.setattr(httpx, "put", fake_put)

    with pytest.raises(cloudflare_dns_adapter.CloudflareError):
        cloudflare_dns_adapter.restore_dns_records()
