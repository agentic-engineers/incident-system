"""Test de concurrencia del deduplicador (issue #12).

Reproduce el escenario real: una tormenta de alertas identicas llegando
en rafaga. El deduplicador DEBERIA devolver un solo incidente.

Requiere Postgres (DATABASE_URL). En rafaga concurrente, el patron
check-then-insert sin proteccion duplica incidentes.
"""
import os
from concurrent.futures import ThreadPoolExecutor

import pytest
from sqlalchemy import create_engine, select, text
from sqlalchemy.orm import sessionmaker

from app.domain import dedup
from app.domain.models import Base, Incident, compute_fingerprint

DATABASE_URL = os.environ.get(
    "DATABASE_URL", "postgresql+psycopg://incidents:incidents@localhost:5432/incidents"
)

pytestmark = pytest.mark.concurrency


@pytest.fixture()
def engine():
    try:
        eng = create_engine(DATABASE_URL, pool_size=20, max_overflow=20)
        with eng.connect() as conn:
            conn.execute(text("SELECT 1"))
    except Exception:
        pytest.skip("Postgres no disponible (levanta deploy/compose/docker-compose.yml)")
    Base.metadata.create_all(eng)
    yield eng
    with eng.begin() as conn:
        conn.execute(text("DELETE FROM incidents"))
    eng.dispose()


def test_burst_of_identical_alerts_creates_single_incident(engine):
    """12 alertas identicas simultaneas -> debe existir UN incidente."""
    import threading

    factory = sessionmaker(bind=engine)
    source, title = "monitor", "disco lleno en web-01 (rafaga)"
    workers = 12
    barrier = threading.Barrier(workers)

    def ingest_once(_):
        session = factory()
        try:
            session.execute(text("SELECT 1"))  # conexion viva antes de la rafaga
            barrier.wait(timeout=10)  # la rafaga llega EN EL MISMO instante
            dedup.ingest_incident(session, source, title)
        finally:
            session.close()

    with ThreadPoolExecutor(max_workers=workers) as pool:
        list(pool.map(ingest_once, range(workers)))

    session = factory()
    try:
        fingerprint = compute_fingerprint(source, title)
        rows = session.execute(
            select(Incident).where(Incident.fingerprint == fingerprint)
        ).scalars().all()
        assert len(rows) == 1, (
            f"se crearon {len(rows)} incidentes para la misma alerta; "
            "el deduplicador no aguanta concurrencia (issue #12)"
        )
    finally:
        session.close()
