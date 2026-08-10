"""Adaptador de notificaciones via Cloudflare (webhook worker)."""
import logging
import os
import time

import httpx

log = logging.getLogger("adapter.cloudflare")

WEBHOOK_URL = os.environ.get("CF_WEBHOOK_URL", "")
MAX_RETRIES = 3


def notify_cloudflare_channel(title: str, body: str) -> bool:
    if not WEBHOOK_URL:
        log.info("cloudflare webhook no configurado, skip")
        return True
    payload = {"title": title, "body": body}
    attempt = 0
    while attempt < MAX_RETRIES:
        try:
            resp = httpx.post(WEBHOOK_URL, json=payload, timeout=5)
            if resp.status_code < 300:
                return True
            log.warning("cloudflare respondio %s, reintentando", resp.status_code)
        except httpx.HTTPError as exc:
            log.warning("error cloudflare: %s, reintentando", exc)
        attempt += 1
        time.sleep(1 * attempt)
    log.error("cloudflare fallo tras %s intentos", MAX_RETRIES)
    return False
