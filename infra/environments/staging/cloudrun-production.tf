# Runtime de production-lab — Cloud Run (escala a cero)
#
# DECISION DE LABORATORIO: production vive en el mismo proyecto y state que staging
# para mantener el lab desechable y barato (borrar proyecto = borrar todo). En una
# empresa real irian en proyectos y states separados.
#
# La PROMOCION no reconstruye nada: despliega el MISMO digest que ya corre en
# staging (ver .github/workflows/promote-production.yml).

resource "google_cloud_run_v2_service" "api_prod" {
  name     = "incident-api-prod"
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
            secret  = google_secret_manager_secret.database_url_production.secret_id
            version = "latest"
          }
        }
      }
      env {
        name  = "APP_VERSION"
        value = "production"
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
  labels = merge(var.labels, { env = "production" })

  lifecycle {
    # El pipeline es dueño del ARTEFACTO desplegado (deploy por digest);
    # Terraform es dueño de la FORMA del servicio.
    ignore_changes = [template[0].containers[0].image]
  }

  depends_on = [
    # La VERSION del secreto (no solo el secreto): Cloud Run valida que
    # "versions/latest" exista al desplegar. Sin esto, carrera en el primer apply.
    google_secret_manager_secret_version.database_url_production,
    google_secret_manager_secret_iam_member.guardia_reads_dburl_production,
    google_project_iam_member.guardia_cloudsql_client,
  ]
}

# Lab: invocable sin auth (recursos desechables, sin datos reales)
resource "google_cloud_run_v2_service_iam_member" "public_invoker_prod" {
  name     = google_cloud_run_v2_service.api_prod.name
  location = var.region
  role     = "roles/run.invoker"
  member   = "allUsers"
}

output "api_prod_url" {
  value = google_cloud_run_v2_service.api_prod.uri
}
