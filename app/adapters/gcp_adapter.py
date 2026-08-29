"""Adaptador de notificaciones via GCP (pubsub push endpoint)."""
import logging
import os

from app.adapters.retry import RETRY_LIMIT, RetryExhaustedError, post_with_retry

log = logging.getLogger("adapter.gcp")

PUSH_URL = os.environ.get("GCP_PUSH_URL", "")


def notify_gcp_channel(title: str, body: str) -> bool:
    if not PUSH_URL:
        log.info("gcp push no configurado, skip")
        return True
    payload = {"title": title, "body": body}
    try:
        post_with_retry(PUSH_URL, payload, log)
        return True
    except RetryExhaustedError:
        log.error("gcp fallo tras %s intentos", RETRY_LIMIT)
        return False
