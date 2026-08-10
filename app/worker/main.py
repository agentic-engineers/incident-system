"""Worker: procesa incidentes en estado 'new'.

Corre en loop, toma incidentes de la cola y notifica por los adaptadores.
"""
import datetime
import logging
import os
import time

from sqlalchemy import select

from app.adapters.cloudflare_adapter import notify_cloudflare_channel
from app.adapters.gcp_adapter import notify_gcp_channel
from app.db import SessionLocal, engine
from app.domain.models import Base, Incident

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("worker")

POLL_SECONDS = float(os.environ.get("WORKER_POLL_SECONDS", "2"))


def process_one(session, incident: Incident) -> None:
    incident.status = "processing"
    session.commit()

    # Notificar por ambos canales.
    notify_cloudflare_channel(incident.title, incident.body)
    notify_gcp_channel(incident.title, incident.body)

    incident.status = "done"
    incident.processed_at = datetime.datetime.utcnow()
    session.commit()


def run_forever() -> None:
    Base.metadata.create_all(bind=engine)
    log.info("worker up")
    while True:
        session = SessionLocal()
        try:
            incident = session.execute(
                select(Incident).where(Incident.status == "new").order_by(Incident.id).limit(1)
            ).scalar_one_or_none()
            if incident is None:
                time.sleep(POLL_SECONDS)
                continue
            log.info("processing incident %s", incident.id)
            process_one(session, incident)
        except Exception:
            log.exception("error procesando")
            time.sleep(POLL_SECONDS)
        finally:
            session.close()


if __name__ == "__main__":
    run_forever()
