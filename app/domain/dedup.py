"""Deduplicación de incidentes.

Si llega un incidente con el mismo fingerprint, devolvemos el existente
en vez de crear otro. Asi evitamos que una tormenta de alertas duplique
tickets.
"""
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.domain.models import AuditEvent, Incident, compute_fingerprint


def ingest_incident(session: Session, source: str, title: str, body: str = "") -> Incident:
    fingerprint = compute_fingerprint(source, title)

    if session.bind.dialect.name == "postgresql":
        # Serializa el check-then-insert por fingerprint: sin esto, una rafaga
        # concurrente de la misma alerta pasa el "no existe" en paralelo y crea
        # un incidente por request (issue #12). Lock de transaccion (se libera
        # solo al hacer commit/rollback), no un constraint de tabla: no puede
        # haber UNIQUE en `fingerprint` porque scripts/legacy_import.py inserta
        # recurrencias repetidas a proposito (ver ese script).
        session.execute(text("SELECT pg_advisory_xact_lock(hashtext(:fp))"), {"fp": fingerprint})

    # 1. ¿Ya existe?
    existing = session.execute(
        select(Incident).where(Incident.fingerprint == fingerprint)
    ).scalar_one_or_none()
    if existing is not None:
        if existing.status == "done":
            # Se reabre: la misma alerta volvio a dispararse despues de resuelta.
            existing.status = "new"
            existing.reopened = True
            session.add(
                AuditEvent(
                    actor=source, action="incident_reopen", detail=f"fingerprint={fingerprint}"
                )
            )
            session.commit()
            session.refresh(existing)
        else:
            session.rollback()  # nada que commitear; libera el advisory lock
        return existing

    # 2. Dejamos rastro de auditoria del ingreso (requerimiento de compliance, 2023).
    session.add(
        AuditEvent(actor=source, action="incident_ingest", detail=f"fingerprint={fingerprint}")
    )

    # 3. No existe: lo creamos.
    incident = Incident(
        fingerprint=fingerprint,
        source=source,
        title=title,
        body=body,
        status="new",
    )
    session.add(incident)
    session.commit()  # commit unico: audit event e incidente atomicos, libera el lock
    session.refresh(incident)
    return incident
