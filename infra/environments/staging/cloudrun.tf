# Runtime de staging — Cloud Run (escala a cero)

variable "api_image" {
  description = "Imagen de la API, SIEMPRE por digest (repo@sha256:...)"
  type        = string
  # placeholder inicial; el pipeline la reemplaza por el digest real
  default = "us-docker.pkg.dev/cloudrun/container/hello"
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
        name = "DATABASE_URL"
        value_source {
          secret_key_ref {
            secret  = google_secret_manager_secret.database_url_staging.secret_id
            version = "latest"
          }
        }
      }
      env {
        name  = "APP_VERSION"
        value = var.env
      }
      volume_mounts {
        name       = "cloudsql"
        mount_path = "/cloudsql"
      }
    }
    volumes {
      name = "cloudsql"
      cloud_sql_instance {
        instances = [google_sql_database_instance.postgres.connection_name]
      }
    }
  }
  labels = var.labels

  lifecycle {
    # El pipeline es dueño del ARTEFACTO desplegado (deploy por digest).
    # Terraform es dueño de la FORMA del servicio (identidad, escala, env).
    ignore_changes = [template[0].containers[0].image]
  }

  depends_on = [
    # La VERSION del secreto (no solo el secreto): Cloud Run valida que
    # "versions/latest" exista al desplegar. Sin esto, carrera en el primer apply.
    google_secret_manager_secret_version.database_url_staging,
    google_secret_manager_secret_iam_member.guardia_reads_dburl_staging,
    google_project_iam_member.guardia_cloudsql_client,
  ]
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
