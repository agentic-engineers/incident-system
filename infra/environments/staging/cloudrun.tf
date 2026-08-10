# Runtime de staging — Cloud Run (escala a cero)

variable "api_image" {
  description = "Imagen de la API, SIEMPRE por digest (repo@sha256:...)"
  type        = string
  # placeholder inicial; el pipeline la reemplaza por el digest real
  default = "us-docker.pkg.dev/cloudrun/container/hello"
}

variable "database_url" {
  description = "URL de la base de datos del ambiente"
  type        = string
  # DECISION PENDIENTE (spike): Postgres de staging.
  # Mientras: sqlite efimero (suficiente para el smoke del thin slice).
  default   = "sqlite:////tmp/staging.db"
  sensitive = true
}

resource "google_cloud_run_v2_service" "api" {
  name     = "incident-api"
  location = var.region

  template {
    service_account = google_service_account.guardia_runtime.email
    scaling {
      min_instance_count = 0
      max_instance_count = 1
    }
    containers {
      image = var.api_image
      env {
        name  = "DATABASE_URL"
        value = var.database_url
      }
      env {
        name  = "APP_VERSION"
        value = var.env
      }
    }
  }
  labels = var.labels
}

# Lab: la API de staging es invocable sin auth (recursos desechables, sin datos reales)
resource "google_cloud_run_v2_service_iam_member" "public_invoker" {
  name     = google_cloud_run_v2_service.api.name
  location = var.region
  role     = "roles/run.invoker"
  member   = "allUsers"
}

output "api_url" {
  value = google_cloud_run_v2_service.api.uri
}
