"""API del sistema de incidentes."""
import os
from enum import Enum

from fastapi import Depends, FastAPI, Query
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db import engine, get_session
from app.domain import dedup
from app.domain.models import Base, Incident

app = FastAPI(title="incident-system")

Base.metadata.create_all(bind=engine)


class IncidentStatus(str, Enum):
    new = "new"
    processing = "processing"
    done = "done"
    failed = "failed"


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

    class Config:
        from_attributes = True


@app.post("/incidents", response_model=IncidentOut)
def create_incident(payload: IncidentIn, session: Session = Depends(get_session)):
    incident = dedup.ingest_incident(session, payload.source, payload.title, payload.body)
    return incident


@app.get("/incidents")
def list_incidents(
    status: IncidentStatus | None = Query(default=None),
    session: Session = Depends(get_session),
):
    query = select(Incident).order_by(Incident.id.desc()).limit(100)
    if status is not None:
        query = query.where(Incident.status == status.value)
    rows = session.execute(query).scalars()
    return [IncidentOut.model_validate(r) for r in rows]


@app.get("/incidents/count")
def count_incidents(session: Session = Depends(get_session)):
    total = session.execute(select(func.count()).select_from(Incident)).scalar_one()
    return {"count": total}


@app.get("/health")
def health():
    # TODO: esto deberia chequear la DB tambien, pero por ahora con esto basta
    return {"status": "ok"}


@app.get("/version")
def version():
    return {
        "version": os.environ.get("APP_VERSION", "dev"),
        "commit": os.environ.get("GIT_SHA", "unknown"),
    }
