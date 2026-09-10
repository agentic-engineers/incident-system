"""API del sistema de incidentes."""
import os

from fastapi import Depends, FastAPI, HTTPException
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.adapters import cloudflare_dns_adapter, gce_adapter
from app.db import engine, get_session
from app.domain import dedup
from app.domain.models import AuditEvent, Base, Incident

app = FastAPI(title="incident-system")

Base.metadata.create_all(bind=engine)


class IncidentIn(BaseModel):
    source: str
    title: str
    body: str = ""


class IncidentOut(BaseModel):
    id: int
    fingerprint: str
    source: str
    title: str
    status: str
    reopened: bool | None = False

    class Config:
        from_attributes = True


class ConfirmRequest(BaseModel):
    confirm: bool = False


@app.post("/incidents", response_model=IncidentOut)
def create_incident(payload: IncidentIn, session: Session = Depends(get_session)):
    incident = dedup.ingest_incident(session, payload.source, payload.title, payload.body)
    return incident


@app.get("/incidents")
def list_incidents(session: Session = Depends(get_session)):
    rows = session.execute(select(Incident).order_by(Incident.id.desc()).limit(100)).scalars()
    return [IncidentOut.model_validate(r) for r in rows]


@app.get("/incidents/count")
def count_incidents(session: Session = Depends(get_session)):
    total = session.execute(select(func.count()).select_from(Incident)).scalar_one()
    return {"count": total}


@app.get("/health")
def health():
    # TODO: esto deberia chequear la DB tambien, pero por ahora con esto basta
    return {"status": "OK"}


@app.get("/version")
def version():
    return {
        "version": os.environ.get("APP_VERSION", "dev"),
        "commit": os.environ.get("GIT_SHA", "unknown"),
    }


@app.get("/infra/vm/status")
def vm_status():
    try:
        status = gce_adapter.get_instance_status()
    except gce_adapter.GceError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return {"instance": gce_adapter.INSTANCE_NAME, "status": status}


@app.post("/infra/vm/start", status_code=202)
def vm_start(payload: ConfirmRequest, session: Session = Depends(get_session)):
    if not payload.confirm:
        raise HTTPException(status_code=400, detail="mutacion: se requiere confirm=true")
    try:
        gce_adapter.start_instance()
    except gce_adapter.GceError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    session.add(
        AuditEvent(actor="guardiactl", action="vm_start", detail=gce_adapter.INSTANCE_NAME)
    )
    session.commit()
    return {"instance": gce_adapter.INSTANCE_NAME, "status": "start_requested"}


@app.get("/infra/dns")
def dns_get():
    try:
        records = cloudflare_dns_adapter.get_dns_records()
    except cloudflare_dns_adapter.CloudflareError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return {"records": records}


@app.post("/infra/dns/restore", status_code=202)
def dns_restore(payload: ConfirmRequest, session: Session = Depends(get_session)):
    if not payload.confirm:
        raise HTTPException(status_code=400, detail="mutacion: se requiere confirm=true")
    try:
        summary = cloudflare_dns_adapter.restore_dns_records()
    except cloudflare_dns_adapter.CloudflareError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    session.add(AuditEvent(actor="guardiactl", action="dns_restore", detail=str(summary)))
    session.commit()
    return summary
