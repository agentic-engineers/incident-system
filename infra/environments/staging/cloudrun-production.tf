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
        name  = "DATABASE_URL"
        value = var.database_url
      }
      env {
        name  = "APP_VERSION"
        value = "production"
      }
    }
  }
  labels = merge(var.labels, { env = "production" })

  lifecycle {
    # El pipeline es dueño del ARTEFACTO desplegado (deploy por digest).
    # Terraform es dueño de la FORMA del servicio (identidad, escala, env).
    ignore_changes = [template[0].containers[0].image]
  }
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
