# Observabilidad del worker — metricas basadas en logs
#
# El worker emite logs estructurados (JSON en stdout) con component="worker"
# (ver app/worker/main.py). Aca esos logs se convierten en metricas de Cloud
# Monitoring: no hace falta agente ni SDK de metricas. Donde sea que corra el
# worker, mientras sus logs lleguen a Cloud Logging, las metricas existen.
#
# Eventos que emite el worker:
#   queue_pending       cada WORKER_QUEUE_METRIC_SECONDS (default 30s), con
#                       jsonPayload.pending (cola en 'new') y .processing
#   incident_processing / incident_done   por incidente, con duration_ms
#   worker_error        severity ERROR, con stacktrace en jsonPayload.exception

# Cola pendiente: gauge muestreado via logs. Las metricas basadas en logs con
# value_extractor son DELTA/DISTRIBUTION; para leerla como gauge, alinear por
# percentil (p50 ≈ el valor muestreado, con una sola instancia de worker).
resource "google_logging_metric" "worker_queue_pending" {
  name        = "worker/queue_pending"
  description = "Incidentes en estado 'new' esperando al worker (muestreado de sus logs)"
  filter      = <<-EOT
    jsonPayload.component="worker"
    jsonPayload.event="queue_pending"
  EOT

  value_extractor = "EXTRACT(jsonPayload.pending)"

  metric_descriptor {
    metric_kind = "DELTA"
    value_type  = "DISTRIBUTION"
    unit        = "1"
  }

  bucket_options {
    exponential_buckets {
      num_finite_buckets = 32
      growth_factor      = 1.5
      scale              = 1
    }
  }
}

# Errores del worker: contador simple sobre severity>=ERROR.
resource "google_logging_metric" "worker_errors" {
  name        = "worker/errors"
  description = "Errores del worker (evento worker_error, severity>=ERROR)"
  filter      = <<-EOT
    jsonPayload.component="worker"
    severity>=ERROR
  EOT

  metric_descriptor {
    metric_kind = "DELTA"
    value_type  = "INT64"
    unit        = "1"
  }
}

variable "worker_queue_alert_threshold" {
  description = "Cola pendiente sostenida a partir de la cual alertar"
  type        = number
  default     = 25
}

# Alerta: cola pendiente sostenida por encima del umbral durante 10 minutos.
# TODO (plataforma): sin notification_channels todavia — la alerta se ve en la
# consola de Monitoring; agregar canal (email/chat) cuando se decida el destino.
resource "google_monitoring_alert_policy" "worker_queue_backlog" {
  display_name = "Worker: cola de incidentes atrasada (${var.env})"
  combiner     = "OR"

  conditions {
    display_name = "queue_pending p50 > ${var.worker_queue_alert_threshold} por 10 min"
    condition_threshold {
      # Sin resource.type a proposito: la metrica hereda el recurso desde donde
      # se emite el log (compose en una VM, Cloud Run, etc.) y la alerta debe
      # funcionar igual en todos.
      filter          = "metric.type=\"logging.googleapis.com/user/${google_logging_metric.worker_queue_pending.name}\""
      comparison      = "COMPARISON_GT"
      threshold_value = var.worker_queue_alert_threshold
      duration        = "600s"

      aggregations {
        alignment_period     = "300s"
        per_series_aligner   = "ALIGN_PERCENTILE_50"
        cross_series_reducer = "REDUCE_MAX"
      }

      trigger {
        count = 1
      }
    }
  }

  documentation {
    content   = "La cola de incidentes pendientes del worker viene creciendo. Diagnostico y pasos: runbooks/worker.md en el repo incident-system."
    mime_type = "text/markdown"
  }

  user_labels = var.labels
}
