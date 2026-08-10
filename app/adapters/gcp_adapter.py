"""Adaptador de notificaciones via GCP (pubsub push endpoint)."""
import logging
import os
import time

import httpx

log = logging.getLogger("adapter.gcp")

PUSH_URL = os.environ.get("GCP_PUSH_URL", "")
RETRY_LIMIT = 3


def notify_gcp_channel(title: str, body: str) -> bool:
    if not PUSH_URL:
        log.info("gcp push no configurado, skip")
        return True
    payload = {"title": title, "body": body}
    tries = 0
    while tries < RETRY_LIMIT:
        try:
            resp = httpx.post(PUSH_URL, json=payload, timeout=5)
            if resp.status_code < 300:
                return True
            log.warning("gcp respondio %s, reintento", resp.status_code)
        except httpx.HTTPError as exc:
            log.warning("error gcp: %s, reintento", exc)
        tries += 1
        time.sleep(1 * tries)
    log.error("gcp fallo tras %s intentos", RETRY_LIMIT)
    return False
