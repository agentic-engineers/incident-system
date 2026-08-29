"""Adaptador de notificaciones via GCP (pubsub push endpoint)."""
import logging
import os
from urllib.parse import urlsplit

from app.adapters.retry import RETRY_LIMIT, RetryExhaustedError, post_with_retry

log = logging.getLogger("adapter.gcp")

PUSH_URL = os.environ.get("GCP_PUSH_URL", "")


def notify_gcp_channel(title: str, body: str) -> bool:
    if not PUSH_URL:
        log.info("gcp push no configurado, skip (incidente=%r)", title)
        return True
    # Solo el host va a los logs: la URL puede traer un token en el path/query.
    host = urlsplit(PUSH_URL).netloc
    payload = {"title": title, "body": body}
    try:
        post_with_retry(PUSH_URL, payload, log)
        return True
    except RetryExhaustedError as exc:
        log.error(
            "gcp (%s) fallo tras %s intentos para incidente=%r: %s",
            host, RETRY_LIMIT, title, exc,
        )
        return False
