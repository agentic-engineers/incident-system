# incident-system — contexto para agentes

## Qué es
API FastAPI + worker de cola + adaptadores (Cloudflare/GCP) sobre Postgres.

## Mapa mínimo
- `app/api/`: endpoints /incidents, /health, /version. **/health es SOLO
  liveness**: no mira la base ni la cola. Verde no significa negocio sano.
- `app/worker/`: loop de polling que consume la cola POR STATUS y notifica
  por los adaptadores.
- `app/domain/models.py`: el CONTRATO de datos. Los estados válidos de un
  incidente están documentados ahí; cualquier estado que veas fuera de ese
  contrato es un hallazgo, no un detalle.
- `app/adapters/`: integraciones externas con retry.
- La dedup se maneja en la capa de servicio (NO hay constraint en la base,
  por compatibilidad con el importador legacy).

## Comandos verificados
- Tests: `PYTHONPATH=. pytest tests/unit -q` · Lint: `ruff check app/ tests/`

## Reglas de operación para agentes
- Ante un incidente, correlaciona SIEMPRE tres fuentes antes de concluir:
  los logs, el estado real de la base, y el código que produce/consume ese
  estado. Una fuente sola es anécdota.
- Cita la evidencia exacta: archivo:línea, query con su resultado, línea de
  log. Sin evidencia citada, no hay conclusión.
- Investigación ≠ arreglo: si la tarea es investigar, NO modifiques código
  ni infraestructura. El diff correcto de una investigación es cero.
