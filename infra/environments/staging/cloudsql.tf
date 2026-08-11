# Base de datos del laboratorio — Cloud SQL (decision 11-ago-2026)
#
# HIBRIDO: el desarrollo (N1-N5) usa el Postgres local de docker-compose (gratis,
# replicable, y donde vive la reproduccion determinstica del issue #12). Staging y
# production comparten UNA instancia minima con una database cada uno (lab barato,
# desechable). En una empresa real: instancia por ambiente.
#
# Tiempos medidos: crear ~11 min · apagar ~1 min · prender ~10 min.
# En reposo se APAGA (activation_policy NEVER a mano): queda solo el costo del disco.

resource "google_sql_database_instance" "postgres" {
  name             = "incident-db"
  database_version = "POSTGRES_16"
  region           = var.region

  settings {
    edition           = "ENTERPRISE" # el default (Enterprise Plus) rechaza db-f1-micro
    tier              = "db-f1-micro"
    disk_type         = "PD_HDD"
    disk_size         = 10
    activation_policy = "ALWAYS"

    ip_configuration {
      # IP publica SIN redes autorizadas: nadie entra por password+IP.
      # El runtime entra por el conector de Cloud SQL con su IDENTIDAD (IAM).
      ipv4_enabled = true
    }

    user_labels = var.labels
  }

  deletion_protection = false # lab desechable
}

resource "google_sql_database" "staging" {
  name     = "incidents_staging"
  instance = google_sql_database_instance.postgres.name
}

resource "google_sql_database" "production" {
  name     = "incidents_prod"
  instance = google_sql_database_instance.postgres.name
}

# Password generada por Terraform. Queda en el state (aceptable en el lab porque el
# state es local y el proyecto desechable; en una empresa: state remoto cifrado).
resource "random_password" "db" {
  length  = 24
  special = false
}

resource "google_sql_user" "incidents" {
  name     = "incidents"
  instance = google_sql_database_instance.postgres.name
  password = random_password.db.result
}

# ── La URL completa vive en Secret Manager; el runtime la lee por identidad ──────

resource "google_secret_manager_secret" "database_url_staging" {
  secret_id = "database-url-staging"
  labels    = var.labels
  replication {
    auto {}
  }
}

resource "google_secret_manager_secret_version" "database_url_staging" {
  secret      = google_secret_manager_secret.database_url_staging.id
  secret_data = "postgresql+psycopg://incidents:${random_password.db.result}@/incidents_staging?host=/cloudsql/${google_sql_database_instance.postgres.connection_name}"
}

resource "google_secret_manager_secret" "database_url_production" {
  secret_id = "database-url-production"
  labels    = var.labels
  replication {
    auto {}
  }
}

resource "google_secret_manager_secret_version" "database_url_production" {
  secret      = google_secret_manager_secret.database_url_production.id
  secret_data = "postgresql+psycopg://incidents:${random_password.db.result}@/incidents_prod?host=/cloudsql/${google_sql_database_instance.postgres.connection_name}"
}

resource "google_secret_manager_secret_iam_member" "guardia_reads_dburl_staging" {
  secret_id = google_secret_manager_secret.database_url_staging.id
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${google_service_account.guardia_runtime.email}"
}

resource "google_secret_manager_secret_iam_member" "guardia_reads_dburl_production" {
  secret_id = google_secret_manager_secret.database_url_production.id
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${google_service_account.guardia_runtime.email}"
}

resource "google_project_iam_member" "guardia_cloudsql_client" {
  project = var.project_id
  role    = "roles/cloudsql.client"
  member  = "serviceAccount:${google_service_account.guardia_runtime.email}"
}

output "db_connection_name" {
  value = google_sql_database_instance.postgres.connection_name
}
