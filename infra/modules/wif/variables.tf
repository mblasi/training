# Variables for Workload Identity Federation module

variable "project_id" {
  description = "GCP Project ID"
  type        = string
}

variable "pool_id" {
  description = "Workload Identity Pool ID"
  type        = string
}

variable "provider_id" {
  description = "Workload Identity Pool Provider ID"
  type        = string
}

variable "service_account_id" {
  description = "Service Account ID to grant workloadIdentityUser role"
  type        = string
}

variable "github_repository" {
  description = "GitHub repository in format owner/repo"
  type        = string
}
