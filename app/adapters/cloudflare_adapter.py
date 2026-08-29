"""Adaptador de notificaciones via Cloudflare (webhook worker)."""
import logging
import os
from urllib.parse import urlsplit

from app.adapters.retry import RETRY_LIMIT, RetryExhaustedError, post_with_retry

log = logging.getLogger("adapter.cloudflare")

WEBHOOK_URL = os.environ.get("CF_WEBHOOK_URL", "")


def notify_cloudflare_channel(title: str, body: str) -> bool:
    if not WEBHOOK_URL:
        log.info("cloudflare webhook no configurado, skip (incidente=%r)", title)
        return True
    # Solo el host va a los logs: la URL puede traer un token en el path/query.
    host = urlsplit(WEBHOOK_URL).netloc
    payload = {"title": title, "body": body}
    try:
        post_with_retry(WEBHOOK_URL, payload, log)
        return True
    except RetryExhaustedError as exc:
        log.error(
            "cloudflare (%s) fallo tras %s intentos para incidente=%r: %s",
            host, RETRY_LIMIT, title, exc,
        )
        return False
