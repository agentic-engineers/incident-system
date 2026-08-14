# Infraestructura de staging — incident-system
# NOTA (2024-08): esto se aplica A MANO desde la maquina de Marcos.
# TODO: moverlo a CI algun dia.

terraform {
  required_version = ">= 1.5"
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 5.0"
    }
    random = {
      source  = "hashicorp/random"
      version = "~> 3.6"
    }
  }
}

variable "project_id" {
  description = "Proyecto GCP del ambiente"
  type        = string
}

variable "region" {
  description = "Region por defecto"
  type        = string
  default     = "us-east1"
}

variable "zone" {
  description = "Zona por defecto"
  type        = string
  default     = "us-east1-b"
}

variable "env" {
  description = "Nombre del ambiente"
  type        = string
  default     = "staging"
}

variable "labels" {
  description = "Etiquetas comunes"
  type        = map(string)
  default = {
    system = "incident-system"
    env    = "staging"
    owner  = "platform"
  }
}

provider "google" {
  project = var.project_id
  region  = var.region
  zone    = var.zone
}

# ── Registro de artefactos (las imagenes se promueven por digest) ──────────────

resource "google_artifact_registry_repository" "images" {
  location      = var.region
  repository_id = "incident-system"
  description   = "Imagenes del sistema de incidentes (promocion por digest)"
  format        = "DOCKER"
  labels        = var.labels
}

# ── La VM objetivo que opera la API de guardia ────────────────────────────────
# Es una maquina separada: la API de guardia NO controla la maquina
# donde ella misma corre (regla de separacion / blast radius).

resource "google_compute_instance" "web_sandbox" {
  name         = "web-sandbox"
  machine_type = "e2-micro"
  zone         = var.zone
  labels       = var.labels

  boot_disk {
    initialize_params {
      image = "debian-cloud/debian-12"
      size  = 10
      type  = "pd-standard"
    }
  }

  network_interface {
    network = "default"
    access_config {} # IP efimera
  }

  allow_stopping_for_update = true
}

# ── Identidad del runtime de la API de guardia ────────────────────────────────
# Minimo privilegio: puede consultar y arrancar SOLO la VM web-sandbox
# (IAM a nivel de INSTANCIA, no de proyecto), y leer sus secretos.

resource "google_service_account" "guardia_runtime" {
  account_id   = "guardia-runtime"
  display_name = "API de guardia (runtime)"
}

resource "google_compute_instance_iam_member" "guardia_can_operate_sandbox" {
  project       = var.project_id
  zone          = var.zone
  instance_name = google_compute_instance.web_sandbox.name
  role          = "roles/compute.instanceAdmin.v1"
  member        = "serviceAccount:${google_service_account.guardia_runtime.email}"
}

# ── Secretos (los VALORES no viven en Terraform ni en git) ────────────────────

resource "google_secret_manager_secret" "cloudflare_token" {
  secret_id = "cloudflare-api-token"
  # TODO: alguien copio esto de otro proyecto, unificar con var.labels algun dia
  labels = {
    system = "incidentes"
    env    = "stg"
    owner  = "platform"
  }
  replication {
    auto {}
  }
}

resource "google_secret_manager_secret_iam_member" "guardia_reads_cf_token" {
  secret_id = google_secret_manager_secret.cloudflare_token.id
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${google_service_account.guardia_runtime.email}"
}

# ── Outputs ───────────────────────────────────────────────────────────────────

output "environment" {
  value = var.env
}

output "web_sandbox_name" {
  value = google_compute_instance.web_sandbox.name
}

output "guardia_runtime_email" {
  value = google_service_account.guardia_runtime.email
}

output "artifact_repo" {
  value = "${var.region}-docker.pkg.dev/${var.project_id}/${google_artifact_registry_repository.images.repository_id}"
}
