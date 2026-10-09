# Variables for Cloud SQL module

variable "project_id" {
  type        = string
  description = "GCP project ID"
}

variable "region" {
  type        = string
  description = "GCP region for Cloud SQL instance"
}

variable "instance_name" {
  type        = string
  description = "Cloud SQL instance name"
}

variable "database_name" {
  type        = string
  description = "Database name to create"
  default     = "trainia"
}

variable "tier" {
  type        = string
  description = "Cloud SQL tier (e.g. db-f1-micro, db-g1-small)"
  default     = "db-f1-micro"
}

variable "service_account_email" {
  type        = string
  description = "Service account email that needs cloudsql.client permissions"
}
