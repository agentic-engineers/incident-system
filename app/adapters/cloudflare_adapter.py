"""Adaptador de notificaciones via Cloudflare (webhook worker)."""
import logging
import os
import time
from urllib.parse import urlsplit

import httpx

log = logging.getLogger("adapter.cloudflare")

WEBHOOK_URL = os.environ.get("CF_WEBHOOK_URL", "")
MAX_RETRIES = 3


def notify_cloudflare_channel(title: str, body: str) -> bool:
    if not WEBHOOK_URL:
        log.info("cloudflare webhook no configurado, skip (incidente=%r)", title)
        return True
    # Solo el host va a los logs: la URL puede traer un token en el path/query.
    host = urlsplit(WEBHOOK_URL).netloc
    payload = {"title": title, "body": body}
    attempt = 0
    last_reason = "sin intentos"
    while attempt < MAX_RETRIES:
        attempt += 1
        try:
            resp = httpx.post(WEBHOOK_URL, json=payload, timeout=5)
            if resp.status_code < 300:
                return True
            last_reason = f"HTTP {resp.status_code}: {resp.text[:200]!r}"
            log.warning(
                "cloudflare (%s) respondio %s en intento %s/%s para incidente=%r: %s",
                host, resp.status_code, attempt, MAX_RETRIES, title, resp.text[:200],
            )
        except httpx.HTTPError as exc:
            last_reason = f"{type(exc).__name__}: {exc}"
            log.warning(
                "cloudflare (%s) fallo en intento %s/%s para incidente=%r: %s",
                host, attempt, MAX_RETRIES, title, last_reason,
            )
        time.sleep(1 * attempt)
    log.error(
        "cloudflare (%s) fallo tras %s intentos para incidente=%r, ultimo error: %s",
        host, MAX_RETRIES, title, last_reason,
    )
    return False
