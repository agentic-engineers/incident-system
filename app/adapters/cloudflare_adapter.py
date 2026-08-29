"""Adaptador de notificaciones via Cloudflare (webhook worker)."""
import logging
import os

from app.adapters.retry import RETRY_LIMIT, RetryExhaustedError, post_with_retry

log = logging.getLogger("adapter.cloudflare")

WEBHOOK_URL = os.environ.get("CF_WEBHOOK_URL", "")


def notify_cloudflare_channel(title: str, body: str) -> bool:
    if not WEBHOOK_URL:
        log.info("cloudflare webhook no configurado, skip")
        return True
    payload = {"title": title, "body": body}
    try:
        post_with_retry(WEBHOOK_URL, payload, log)
        return True
    except RetryExhaustedError:
        log.error("cloudflare fallo tras %s intentos", RETRY_LIMIT)
        return False
