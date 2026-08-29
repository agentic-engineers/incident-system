"""Adaptador de notificaciones via GCP (pubsub push endpoint)."""
import logging
import os
import time
from urllib.parse import urlsplit

import httpx

log = logging.getLogger("adapter.gcp")

PUSH_URL = os.environ.get("GCP_PUSH_URL", "")
RETRY_LIMIT = 3


def notify_gcp_channel(title: str, body: str) -> bool:
    if not PUSH_URL:
        log.info("gcp push no configurado, skip (incidente=%r)", title)
        return True
    # Solo el host va a los logs: la URL puede traer un token en el path/query.
    host = urlsplit(PUSH_URL).netloc
    payload = {"title": title, "body": body}
    tries = 0
    last_reason = "sin intentos"
    while tries < RETRY_LIMIT:
        tries += 1
        try:
            resp = httpx.post(PUSH_URL, json=payload, timeout=5)
            if resp.status_code < 300:
                return True
            last_reason = f"HTTP {resp.status_code}: {resp.text[:200]!r}"
            log.warning(
                "gcp (%s) respondio %s en intento %s/%s para incidente=%r: %s",
                host, resp.status_code, tries, RETRY_LIMIT, title, resp.text[:200],
            )
        except httpx.HTTPError as exc:
            last_reason = f"{type(exc).__name__}: {exc}"
            log.warning(
                "gcp (%s) fallo en intento %s/%s para incidente=%r: %s",
                host, tries, RETRY_LIMIT, title, last_reason,
            )
        time.sleep(1 * tries)
    log.error(
        "gcp (%s) fallo tras %s intentos para incidente=%r, ultimo error: %s",
        host, RETRY_LIMIT, title, last_reason,
    )
    return False
