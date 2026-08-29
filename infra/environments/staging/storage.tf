# ── Bucket de reportes de estado — API de guardia ──────────────────────────────
# Exports JSON de la API de guardia (poco volumen). Privado: sin acceso publico,
# uniform bucket-level access, IAM explicito solo para la identidad de runtime
# (mismo patron de minimo privilegio que el compute_instance_iam_member de
# web_sandbox en main.tf: el permiso queda scoped al recurso, no al proyecto).

resource "google_storage_bucket" "guardia_reports" {
  name          = "${var.project_id}-guardia-reports"
  location      = var.region
  storage_class = "STANDARD"
  labels        = var.labels

  uniform_bucket_level_access = true
  public_access_prevention    = "enforced"
}

resource "google_storage_bucket_iam_member" "guardia_writes_reports" {
  bucket = google_storage_bucket.guardia_reports.name
  role   = "roles/storage.objectAdmin"
  member = "serviceAccount:${google_service_account.guardia_runtime.email}"
}

output "guardia_reports_bucket" {
  value = google_storage_bucket.guardia_reports.name
}
