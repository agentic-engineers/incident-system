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
  }
}

variable "project_id" {
  description = "Proyecto GCP del laboratorio"
  type        = string
}

variable "region" {
  description = "Region por defecto"
  type        = string
  default     = "us-central1"
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
}

# La VM objetivo que la API de guardia va a operar (caso 3 del curso)
# se agrega durante el curso. Este modulo parte minimo a proposito.

output "environment" {
  value = var.env
}
