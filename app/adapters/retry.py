"""Retry compartido para adaptadores de notificación HTTP.

Contrato de retry policy (CONGELADO, no modificar):
- RETRY_LIMIT intentos (3).
- Backoff lineal: se duerme `1 * numero_de_intento` segundos tras cada
  intento fallido, incluido el ultimo.
- REQUEST_TIMEOUT por request (5s).
- Se reintenta ante status_code >= 300 o httpx.HTTPError.
"""
import logging
import time

import httpx

RETRY_LIMIT = 3
REQUEST_TIMEOUT = 5


class NotificationError(Exception):
    """Error base de notificación via un adaptador HTTP."""


class NotificationHTTPError(NotificationError):
    """El endpoint respondio con un status_code de error (>=300)."""

    def __init__(self, status_code: int):
        self.status_code = status_code
        super().__init__(f"respuesta HTTP {status_code}")


class NotificationConnectionError(NotificationError):
    """Fallo de red/conexion al llamar al endpoint."""

    def __init__(self, cause: httpx.HTTPError):
        self.cause = cause
        super().__init__(str(cause))


class RetryExhaustedError(NotificationError):
    """Se agotaron los RETRY_LIMIT intentos sin éxito."""

    def __init__(self, attempts: int, last_error: NotificationError):
        self.attempts = attempts
        self.last_error = last_error
        super().__init__(f"fallo tras {attempts} intentos: {last_error}")


def post_with_retry(url: str, payload: dict, log: logging.Logger) -> None:
    """POSTea `payload` a `url` con la retry policy congelada.

    No retorna nada en éxito. Levanta RetryExhaustedError si se agotan
    los intentos.
    """
    last_error: NotificationError | None = None
    tries = 0
    while tries < RETRY_LIMIT:
        try:
            resp = httpx.post(url, json=payload, timeout=REQUEST_TIMEOUT)
            if resp.status_code < 300:
                return
            last_error = NotificationHTTPError(resp.status_code)
            log.warning("respondio %s, reintento", resp.status_code)
        except httpx.HTTPError as exc:
            last_error = NotificationConnectionError(exc)
            log.warning("error de red: %s, reintento", exc)
        tries += 1
        time.sleep(1 * tries)
    raise RetryExhaustedError(RETRY_LIMIT, last_error)
