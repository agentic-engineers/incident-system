"""Test del formato de timestamp en los logs del worker (ISO 8601 UTC)."""
import json
import logging
import re

from app.worker.main import JsonFormatter

ISO_8601_UTC = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}Z$")


def _format(created: float) -> dict:
    record = logging.LogRecord("worker", logging.INFO, "", 0, "hola", (), None)
    record.created = created
    return json.loads(JsonFormatter().format(record))


def test_timestamp_es_iso8601_utc():
    payload = _format(1_700_000_000.123456)
    assert ISO_8601_UTC.match(payload["timestamp"])


def test_timestamp_es_consistente_sin_microsegundos():
    # Cuando el timestamp cae en un segundo exacto (microsecond=0), el
    # formato no debe cambiar (antes se omitian los milisegundos).
    payload = _format(1_700_000_000.0)
    assert ISO_8601_UTC.match(payload["timestamp"])
