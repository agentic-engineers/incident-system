"""Worker: procesa incidentes en estado 'new'.

Corre en loop, toma incidentes de la cola y notifica por los adaptadores.

Observabilidad: emite logs estructurados (una linea JSON por evento, a stdout).
Cloud Logging los parsea directo y promueve severity/timestamp/message; el resto
queda en jsonPayload. La metrica de cola pendiente se construye sobre el evento
`queue_pending` (ver infra/environments/staging/observability.tf y
runbooks/worker.md).
"""
import datetime
import json
import logging
import os
import time

from sqlalchemy import func, select

from app.adapters.cloudflare_adapter import notify_cloudflare_channel
from app.adapters.gcp_adapter import notify_gcp_channel
from app.db import SessionLocal, engine
from app.domain.models import Base, Incident

POLL_SECONDS = float(os.environ.get("WORKER_POLL_SECONDS", "2"))
# Cada cuanto se emite el evento queue_pending (la metrica). Independiente del
# poll para no generar una linea de log cada 2 segundos.
QUEUE_METRIC_SECONDS = float(os.environ.get("WORKER_QUEUE_METRIC_SECONDS", "30"))

# Atributos que trae todo LogRecord; lo que no este aca vino via extra={...}.
_RESERVED = set(logging.LogRecord("", 0, "", 0, "", (), None).__dict__) | {
    "message",
    "asctime",
}


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "timestamp": datetime.datetime.fromtimestamp(
                record.created, tz=datetime.timezone.utc
            ).isoformat(),
            "severity": record.levelname,
            "component": "worker",
            "message": record.getMessage(),
        }
        payload.update(
            {k: v for k, v in record.__dict__.items() if k not in _RESERVED}
        )
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, default=str)


_handler = logging.StreamHandler()
_handler.setFormatter(JsonFormatter())
logging.basicConfig(level=logging.INFO, handlers=[_handler])
log = logging.getLogger("worker")


def queue_counts(session) -> tuple[int, int]:
    """(pendientes en 'new', atascados o en curso en 'processing')."""
    rows = dict(
        session.execute(
            select(Incident.status, func.count())
            .where(Incident.status.in_(["new", "processing"]))
            .group_by(Incident.status)
        ).all()
    )
    return rows.get("new", 0), rows.get("processing", 0)


def process_one(session, incident: Incident) -> None:
    started = time.monotonic()
    log.info(
        "incident %s: processing",
        incident.id,
        extra={
            "event": "incident_processing",
            "incident_id": incident.id,
            "incident_source": incident.source,
        },
    )
    incident.status = "processing"
    session.commit()

    # Notificar por ambos canales.
    notify_cloudflare_channel(incident.title, incident.body)
    notify_gcp_channel(incident.title, incident.body)

    incident.status = "done"
    incident.processed_at = datetime.datetime.utcnow()
    session.commit()
    log.info(
        "incident %s: done",
        incident.id,
        extra={
            "event": "incident_done",
            "incident_id": incident.id,
            "duration_ms": round((time.monotonic() - started) * 1000),
        },
    )


def run_forever() -> None:
    Base.metadata.create_all(bind=engine)
    log.info(
        "worker up",
        extra={
            "event": "worker_up",
            "poll_seconds": POLL_SECONDS,
            "queue_metric_seconds": QUEUE_METRIC_SECONDS,
        },
    )
    last_metric = float("-inf")
    while True:
        session = SessionLocal()
        incident_id = None
        try:
            if time.monotonic() - last_metric >= QUEUE_METRIC_SECONDS:
                pending, processing = queue_counts(session)
                log.info(
                    "queue pending=%s processing=%s",
                    pending,
                    processing,
                    extra={
                        "event": "queue_pending",
                        "pending": pending,
                        "processing": processing,
                    },
                )
                last_metric = time.monotonic()
            incident = session.execute(
                select(Incident).where(Incident.status == "new").order_by(Incident.id).limit(1)
            ).scalar_one_or_none()
            if incident is None:
                time.sleep(POLL_SECONDS)
                continue
            incident_id = incident.id
            process_one(session, incident)
        except Exception:
            log.exception(
                "error procesando",
                extra={"event": "worker_error", "incident_id": incident_id},
            )
            time.sleep(POLL_SECONDS)
        finally:
            session.close()


if __name__ == "__main__":
    run_forever()
