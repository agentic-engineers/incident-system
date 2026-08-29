"""Adaptador de Compute Engine para operar la VM web-sandbox (API de guardia).

Unica instancia permitida: la allowlist es intencional y espeja el IAM de
`guardia-runtime` en infra/environments/staging/main.tf, que esta acotado a
esta misma instancia (get + start), nunca a nivel de proyecto.
"""
import logging
import os
import time

import httpx

log = logging.getLogger("adapter.gce")

PROJECT_ID = os.environ.get("GCP_PROJECT_ID", "")
ZONE = os.environ.get("GCE_ZONE", "us-east1-b")
INSTANCE_NAME = "web-sandbox"
ALLOWED_INSTANCES = {"web-sandbox"}

MAX_RETRIES = 3
_METADATA_TOKEN_URL = (
    "http://metadata.google.internal/computeMetadata/v1/"
    "instance/service-accounts/default/token"
)


class GceError(Exception):
    """La API de Compute no respondio correctamente tras los reintentos."""


def get_metadata_token() -> str:
    resp = httpx.get(_METADATA_TOKEN_URL, headers={"Metadata-Flavor": "Google"}, timeout=5)
    resp.raise_for_status()
    return resp.json()["access_token"]


def _instance_url(instance: str) -> str:
    return (
        f"https://compute.googleapis.com/compute/v1/projects/{PROJECT_ID}"
        f"/zones/{ZONE}/instances/{instance}"
    )


def _instance_action_url(instance: str, action: str) -> str:
    return f"{_instance_url(instance)}/{action}"


def get_instance_status(instance: str = INSTANCE_NAME) -> str:
    if instance not in ALLOWED_INSTANCES:
        raise GceError(f"instancia no permitida: {instance!r}")

    try:
        token = get_metadata_token()
    except httpx.HTTPError as exc:
        raise GceError(f"no se pudo obtener token de metadata: {exc}") from exc

    url = _instance_url(instance)
    attempt = 0
    last_reason = "sin intentos"
    while attempt < MAX_RETRIES:
        attempt += 1
        try:
            resp = httpx.get(url, headers={"Authorization": f"Bearer {token}"}, timeout=5)
            if resp.status_code < 300:
                return resp.json()["status"]
            last_reason = f"HTTP {resp.status_code}: {resp.text[:200]!r}"
            log.warning(
                "gce status fallo en intento %s/%s para %s: %s",
                attempt, MAX_RETRIES, instance, last_reason,
            )
        except httpx.HTTPError as exc:
            last_reason = f"{type(exc).__name__}: {exc}"
            log.warning(
                "gce status fallo en intento %s/%s para %s: %s",
                attempt, MAX_RETRIES, instance, last_reason,
            )
        time.sleep(1 * attempt)
    log.error("gce status fallo tras %s intentos para %s: %s", MAX_RETRIES, instance, last_reason)
    raise GceError(last_reason)


def start_instance(instance: str = INSTANCE_NAME) -> bool:
    if instance not in ALLOWED_INSTANCES:
        raise GceError(f"instancia no permitida: {instance!r}")

    try:
        token = get_metadata_token()
    except httpx.HTTPError as exc:
        raise GceError(f"no se pudo obtener token de metadata: {exc}") from exc

    url = _instance_action_url(instance, "start")
    attempt = 0
    last_reason = "sin intentos"
    while attempt < MAX_RETRIES:
        attempt += 1
        try:
            resp = httpx.post(url, headers={"Authorization": f"Bearer {token}"}, timeout=5)
            if resp.status_code < 300:
                return True
            last_reason = f"HTTP {resp.status_code}: {resp.text[:200]!r}"
            log.warning(
                "gce start fallo en intento %s/%s para %s: %s",
                attempt, MAX_RETRIES, instance, last_reason,
            )
        except httpx.HTTPError as exc:
            last_reason = f"{type(exc).__name__}: {exc}"
            log.warning(
                "gce start fallo en intento %s/%s para %s: %s",
                attempt, MAX_RETRIES, instance, last_reason,
            )
        time.sleep(1 * attempt)
    log.error("gce start fallo tras %s intentos para %s: %s", MAX_RETRIES, instance, last_reason)
    raise GceError(last_reason)
