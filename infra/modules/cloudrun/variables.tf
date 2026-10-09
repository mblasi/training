# Variables for Cloud Run module

variable "project_id" {
  description = "GCP project ID"
  type        = string
}

variable "region" {
  description = "GCP region"
  type        = string
}

variable "service_name" {
  description = "Name of the Cloud Run service"
  type        = string
  default     = "api"
}

variable "image" {
  description = "Container image URL"
  type        = string
}

variable "database_url_secret_name" {
  description = "Full resource name of the DATABASE_URL secret in Secret Manager"
  type        = string
}

variable "firebase_project_id" {
  description = "Firebase project ID"
  type        = string
}

variable "admin_emails" {
  description = "Comma-separated list of admin emails"
  type        = string
}

variable "cloud_sql_connection_name" {
  description = "Cloud SQL instance connection name for Unix socket"
  type        = string
}

variable "domain" {
  description = "Custom domain for Cloud Run service"
  type        = string
  default     = ""
}
