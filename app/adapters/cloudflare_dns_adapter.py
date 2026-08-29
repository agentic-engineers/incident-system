"""Adaptador de DNS via Cloudflare (API de guardia).

Solo lectura y "restore" (upsert contra una lista permitida de registros
conocidos-buenos, ver KNOWN_GOOD_RECORDS). Deliberadamente no existe ninguna
operacion de borrado en este modulo.
"""
import json
import logging
import os
import time

import httpx

log = logging.getLogger("adapter.cloudflare_dns")

CF_API_TOKEN = os.environ.get("CF_API_TOKEN", "")
CF_ZONE_ID = os.environ.get("CF_ZONE_ID", "")

# Lista permitida de registros "conocidos-buenos": restore() solo crea o
# actualiza registros presentes aca. Cualquier registro en Cloudflare que no
# figure en esta lista queda intacto (no hay operacion de borrado).
KNOWN_GOOD_RECORDS: list[dict] = json.loads(os.environ.get("CF_DNS_SNAPSHOT_JSON", "[]"))

MAX_RETRIES = 3
_API_BASE = "https://api.cloudflare.com/client/v4"


class CloudflareError(Exception):
    """La API de Cloudflare no respondio correctamente tras los reintentos."""


def _headers() -> dict:
    return {"Authorization": f"Bearer {CF_API_TOKEN}"}


def get_dns_records() -> list[dict]:
    url = f"{_API_BASE}/zones/{CF_ZONE_ID}/dns_records"
    attempt = 0
    last_reason = "sin intentos"
    while attempt < MAX_RETRIES:
        attempt += 1
        try:
            resp = httpx.get(url, headers=_headers(), timeout=5)
            if resp.status_code < 300:
                return [
                    {"id": r["id"], "name": r["name"], "type": r["type"], "content": r["content"]}
                    for r in resp.json()["result"]
                ]
            last_reason = f"HTTP {resp.status_code}: {resp.text[:200]!r}"
            log.warning(
                "cloudflare dns get fallo en intento %s/%s: %s",
                attempt, MAX_RETRIES, last_reason,
            )
        except httpx.HTTPError as exc:
            last_reason = f"{type(exc).__name__}: {exc}"
            log.warning(
                "cloudflare dns get fallo en intento %s/%s: %s",
                attempt, MAX_RETRIES, last_reason,
            )
        time.sleep(1 * attempt)
    log.error("cloudflare dns get fallo tras %s intentos: %s", MAX_RETRIES, last_reason)
    raise CloudflareError(last_reason)


def _update_record(record_id: str, name: str, type_: str, content: str) -> None:
    url = f"{_API_BASE}/zones/{CF_ZONE_ID}/dns_records/{record_id}"
    payload = {"type": type_, "name": name, "content": content}
    attempt = 0
    last_reason = "sin intentos"
    while attempt < MAX_RETRIES:
        attempt += 1
        try:
            resp = httpx.put(url, headers=_headers(), json=payload, timeout=5)
            if resp.status_code < 300:
                return
            last_reason = f"HTTP {resp.status_code}: {resp.text[:200]!r}"
            log.warning(
                "cloudflare dns update fallo en intento %s/%s para %s: %s",
                attempt, MAX_RETRIES, name, last_reason,
            )
        except httpx.HTTPError as exc:
            last_reason = f"{type(exc).__name__}: {exc}"
            log.warning(
                "cloudflare dns update fallo en intento %s/%s para %s: %s",
                attempt, MAX_RETRIES, name, last_reason,
            )
        time.sleep(1 * attempt)
    log.error(
        "cloudflare dns update fallo tras %s intentos para %s: %s", MAX_RETRIES, name, last_reason
    )
    raise CloudflareError(last_reason)


def _create_record(name: str, type_: str, content: str) -> None:
    url = f"{_API_BASE}/zones/{CF_ZONE_ID}/dns_records"
    payload = {"type": type_, "name": name, "content": content}
    attempt = 0
    last_reason = "sin intentos"
    while attempt < MAX_RETRIES:
        attempt += 1
        try:
            resp = httpx.post(url, headers=_headers(), json=payload, timeout=5)
            if resp.status_code < 300:
                return
            last_reason = f"HTTP {resp.status_code}: {resp.text[:200]!r}"
            log.warning(
                "cloudflare dns create fallo en intento %s/%s para %s: %s",
                attempt, MAX_RETRIES, name, last_reason,
            )
        except httpx.HTTPError as exc:
            last_reason = f"{type(exc).__name__}: {exc}"
            log.warning(
                "cloudflare dns create fallo en intento %s/%s para %s: %s",
                attempt, MAX_RETRIES, name, last_reason,
            )
        time.sleep(1 * attempt)
    log.error(
        "cloudflare dns create fallo tras %s intentos para %s: %s", MAX_RETRIES, name, last_reason
    )
    raise CloudflareError(last_reason)


def restore_dns_records() -> dict:
    """Corrige drift contra KNOWN_GOOD_RECORDS.

    Nunca borra: solo crea los registros permitidos que faltan y actualiza
    los que difieren. Un registro vivo que no figura en KNOWN_GOOD_RECORDS
    no se toca.
    """
    live_by_key = {(r["name"], r["type"]): r for r in get_dns_records()}

    restored: list[str] = []
    created: list[str] = []
    unchanged: list[str] = []
    for expected in KNOWN_GOOD_RECORDS:
        key = (expected["name"], expected["type"])
        live_record = live_by_key.get(key)
        if live_record is None:
            _create_record(expected["name"], expected["type"], expected["content"])
            created.append(expected["name"])
        elif live_record["content"] != expected["content"]:
            _update_record(
                live_record["id"], expected["name"], expected["type"], expected["content"]
            )
            restored.append(expected["name"])
        else:
            unchanged.append(expected["name"])

    return {"restored": restored, "created": created, "unchanged": unchanged}
