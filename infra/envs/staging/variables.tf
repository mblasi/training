# Variables for staging environment

variable "project_id" {
  description = "GCP project ID"
  type        = string
}

variable "region" {
  description = "GCP region"
  type        = string
  default     = "us-central1"
}

variable "image_tag" {
  description = "Docker image tag for the API"
  type        = string
}

variable "api_min_instances" {
  description = "Minimum number of Cloud Run instances for the API"
  type        = number
  default     = 0
}
