# Variables for Secret Manager module

variable "project_id" {
  description = "GCP project ID"
  type        = string
}

variable "service_account_email" {
  description = "Service account email that needs access to secrets"
  type        = string
}
