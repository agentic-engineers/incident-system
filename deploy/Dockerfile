FROM python:3.12-slim AS base

WORKDIR /srv/incident-system

COPY pyproject.toml ./
RUN pip install --no-cache-dir . 2>/dev/null || pip install --no-cache-dir \
    fastapi uvicorn "sqlalchemy>=2.0" "psycopg[binary]" httpx pydantic

COPY app/ ./app/

ARG GIT_SHA=unknown
ENV GIT_SHA=${GIT_SHA}
ENV PYTHONPATH=/srv/incident-system

EXPOSE 8000

# api por defecto; el worker usa el mismo artefacto con otro comando.
# PORT lo inyecta el runtime (Cloud Run usa 8080); default 8000 en local.
CMD exec uvicorn app.api.main:app --host 0.0.0.0 --port ${PORT:-8000}
