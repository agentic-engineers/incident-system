"""Deduplicación de incidentes.

Si llega un incidente con el mismo fingerprint, devolvemos el existente
en vez de crear otro. Asi evitamos que una tormenta de alertas duplique
tickets.
"""
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domain.models import AuditEvent, Incident, compute_fingerprint


def ingest_incident(session: Session, source: str, title: str, body: str = "") -> Incident:
    fingerprint = compute_fingerprint(source, title)

    # 1. ¿Ya existe?
    existing = session.execute(
        select(Incident).where(Incident.fingerprint == fingerprint)
    ).scalar_one_or_none()
    if existing is not None:
        return existing

    # 2. Dejamos rastro de auditoria del ingreso (requerimiento de compliance, 2023).
    session.add(
        AuditEvent(actor=source, action="incident_ingest", detail=f"fingerprint={fingerprint}")
    )
    session.commit()

    # 3. No existe: lo creamos.
    incident = Incident(
        fingerprint=fingerprint,
        source=source,
        title=title,
        body=body,
        status="new",
    )
    session.add(incident)
    session.commit()
    session.refresh(incident)
    return incident
