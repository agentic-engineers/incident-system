"""Tests del retry compartido de adaptadores y de su uso en gcp/cloudflare."""
import logging

import httpx
import pytest

from app.adapters import cloudflare_adapter, gcp_adapter
from app.adapters import retry as retry_mod
from app.adapters.retry import (
    NotificationConnectionError,
    NotificationHTTPError,
    RetryExhaustedError,
    post_with_retry,
)


class FakeResponse:
    def __init__(self, status_code):
        self.status_code = status_code


@pytest.fixture(autouse=True)
def no_sleep(monkeypatch):
    sleeps = []
    monkeypatch.setattr(retry_mod.time, "sleep", lambda s: sleeps.append(s))
    return sleeps


def test_contrato_de_retry_congelado():
    assert retry_mod.RETRY_LIMIT == 3
    assert retry_mod.REQUEST_TIMEOUT == 5


def test_post_with_retry_exito_primer_intento(monkeypatch, no_sleep):
    calls = []

    def fake_post(url, json, timeout):
        calls.append((url, json, timeout))
        return FakeResponse(200)

    monkeypatch.setattr(retry_mod.httpx, "post", fake_post)
    post_with_retry("http://x", {"a": 1}, logging.getLogger("t"))

    assert len(calls) == 1
    assert calls[0] == ("http://x", {"a": 1}, retry_mod.REQUEST_TIMEOUT)
    assert no_sleep == []


def test_post_with_retry_exito_tras_status_de_error(monkeypatch, no_sleep):
    responses = iter([FakeResponse(500), FakeResponse(200)])
    monkeypatch.setattr(retry_mod.httpx, "post", lambda url, json, timeout: next(responses))

    post_with_retry("http://x", {}, logging.getLogger("t"))

    assert no_sleep == [1]


def test_post_with_retry_exito_tras_error_de_red(monkeypatch, no_sleep):
    calls = {"n": 0}

    def fake_post(url, json, timeout):
        calls["n"] += 1
        if calls["n"] == 1:
            raise httpx.ConnectError("boom")
        return FakeResponse(200)

    monkeypatch.setattr(retry_mod.httpx, "post", fake_post)
    post_with_retry("http://x", {}, logging.getLogger("t"))

    assert no_sleep == [1]


def test_post_with_retry_agota_intentos_por_status(monkeypatch, no_sleep):
    monkeypatch.setattr(retry_mod.httpx, "post", lambda url, json, timeout: FakeResponse(503))

    with pytest.raises(RetryExhaustedError) as exc_info:
        post_with_retry("http://x", {}, logging.getLogger("t"))

    err = exc_info.value
    assert err.attempts == retry_mod.RETRY_LIMIT
    assert isinstance(err.last_error, NotificationHTTPError)
    assert err.last_error.status_code == 503
    # backoff lineal 1,2,3 -- incluye el sleep tras el ultimo intento fallido.
    assert no_sleep == [1, 2, 3]


def test_post_with_retry_agota_intentos_por_error_de_red(monkeypatch, no_sleep):
    def fake_post(url, json, timeout):
        raise httpx.ConnectTimeout("timeout")

    monkeypatch.setattr(retry_mod.httpx, "post", fake_post)

    with pytest.raises(RetryExhaustedError) as exc_info:
        post_with_retry("http://x", {}, logging.getLogger("t"))

    assert isinstance(exc_info.value.last_error, NotificationConnectionError)
    assert no_sleep == [1, 2, 3]


ADAPTERS = [
    (gcp_adapter, "notify_gcp_channel", "PUSH_URL"),
    (cloudflare_adapter, "notify_cloudflare_channel", "WEBHOOK_URL"),
]


@pytest.mark.parametrize("module, fn_name, url_attr", ADAPTERS)
def test_adapter_skip_si_no_configurado(monkeypatch, module, fn_name, url_attr):
    monkeypatch.setattr(module, url_attr, "")
    notify_fn = getattr(module, fn_name)

    assert notify_fn("titulo", "cuerpo") is True


@pytest.mark.parametrize("module, fn_name, url_attr", ADAPTERS)
def test_adapter_true_en_exito(monkeypatch, module, fn_name, url_attr, no_sleep):
    monkeypatch.setattr(module, url_attr, "http://configurado")
    monkeypatch.setattr(retry_mod.httpx, "post", lambda url, json, timeout: FakeResponse(204))
    notify_fn = getattr(module, fn_name)

    assert notify_fn("titulo", "cuerpo") is True
    assert no_sleep == []


@pytest.mark.parametrize("module, fn_name, url_attr", ADAPTERS)
def test_adapter_false_tras_agotar_reintentos(monkeypatch, module, fn_name, url_attr, no_sleep):
    monkeypatch.setattr(module, url_attr, "http://configurado")
    monkeypatch.setattr(retry_mod.httpx, "post", lambda url, json, timeout: FakeResponse(500))
    notify_fn = getattr(module, fn_name)

    assert notify_fn("titulo", "cuerpo") is False
    assert no_sleep == [1, 2, 3]
