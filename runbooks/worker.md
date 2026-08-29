# Operación del worker

El worker (`app/worker/main.py`) corre en loop: toma incidentes en estado
`new` de a uno, notifica por los adaptadores y los marca `done`. Es una sola
instancia; si se cae, la cola simplemente se acumula (no se pierde nada).

## Qué emite

Logs estructurados: una línea JSON por evento, a stdout, siempre con
`component="worker"` y timestamp UTC. Eventos:

| `event` | Cuándo | Campos útiles |
|---|---|---|
| `worker_up` | Al arrancar | `poll_seconds`, `queue_metric_seconds` |
| `queue_pending` | Cada 30s (configurable con `WORKER_QUEUE_METRIC_SECONDS`) | `pending` (cola en `new`), `processing` |
| `incident_processing` | Al tomar un incidente | `incident_id`, `incident_source` |
| `incident_done` | Al terminarlo | `incident_id`, `duration_ms` |
| `worker_error` | Ante cualquier excepción (severity ERROR) | `incident_id` (puede ser null), `exception` con stacktrace |

## Métricas y alerta (Cloud Monitoring)

Definidas en `infra/environments/staging/observability.tf` (se aplican a mano
desde la máquina de Marcos, como el resto del terraform):

- **`logging.googleapis.com/user/worker/queue_pending`** — cola pendiente,
  muestreada del evento `queue_pending`. Es una distribución: en Metrics
  Explorer leerla con alineador *p50* (con una sola instancia de worker, el
  p50 es el valor muestreado).
- **`logging.googleapis.com/user/worker/errors`** — contador de errores.
- **Alerta "Worker: cola de incidentes atrasada"** — dispara si `pending`
  se sostiene por encima de 25 (variable `worker_queue_alert_threshold`)
  durante 10 minutos. Todavía sin canal de notificación: se ve en la consola
  de Monitoring.

Las métricas funcionan donde sea que el worker corra, mientras sus logs
lleguen a Cloud Logging.

## Cómo mirar

**Cola pendiente ahora mismo** (fuente de verdad, directo en la DB):

```sql
SELECT status, count(*) FROM incidents
WHERE status IN ('new', 'processing') GROUP BY status;
```

**Logs en local / compose:**

```bash
docker compose -f deploy/compose/docker-compose.yml logs -f worker
```

**Logs en GCP:**

```bash
# Todo lo del worker, lo más reciente primero
gcloud logging read 'jsonPayload.component="worker"' --limit 50

# Solo errores
gcloud logging read 'jsonPayload.component="worker" severity>=ERROR' --limit 20

# Seguimiento de un incidente puntual
gcloud logging read 'jsonPayload.component="worker" jsonPayload.incident_id=123'
```

## Si la cola crece

1. **¿El worker está vivo?** Buscar el último `queue_pending` o `worker_up`
   en los logs. Si el último log tiene más de un par de minutos, el worker
   está caído: reiniciar el servicio (`docker compose restart worker` en
   compose) y la cola se drena sola.
2. **¿Está fallando en loop?** Mirar `severity>=ERROR`. Un `worker_error`
   repetido con el mismo `incident_id` significa un incidente venenoso que
   bloquea la cola (el worker procesa en orden, de a uno). Revisar el
   stacktrace; si el incidente es basura, marcarlo a mano:

   ```sql
   UPDATE incidents SET status = 'failed' WHERE id = <id>;
   ```

3. **¿Hay incidentes atascados en `processing`?** Si el worker murió a mitad
   de un incidente, ese queda en `processing` para siempre (el worker solo
   toma `new`). Con el worker **detenido**, reencolar:

   ```sql
   UPDATE incidents SET status = 'new' WHERE status = 'processing';
   ```

   Ojo: los adaptadores pueden notificar dos veces ese incidente; hoy no hay
   idempotencia en la notificación.
4. **¿Simplemente entra más de lo que sale?** `duration_ms` en los eventos
   `incident_done` dice cuánto tarda cada uno. Si los adaptadores están
   lentos, la cola crece aunque todo esté "sano".
