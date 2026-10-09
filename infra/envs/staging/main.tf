terraform {
  required_version = ">= 1.8.0"
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 6.0"
    }
  }
}

provider "google" {
  project = var.project_id
  region  = var.region
}

# Service account for Cloud Run API service
resource "google_service_account" "api" {
  account_id   = "trainia-api"
  display_name = "Trainia API Service Account"
  description  = "Service account for Cloud Run API service"
}

# Cloud SQL module
module "cloudsql" {
  source = "../../modules/cloudsql"

  project_id            = var.project_id
  region                = var.region
  instance_name         = "trainia-staging"
  database_name         = "trainia"
  tier                  = "db-f1-micro"
  service_account_email = google_service_account.api.email
}

# Secrets module
module "secrets" {
  source = "../../modules/secrets"

  project_id            = var.project_id
  service_account_email = google_service_account.api.email
}

# Workload Identity Federation module
module "wif" {
  source = "../../modules/wif"

  project_id         = var.project_id
  pool_id            = "github-actions"
  provider_id        = "github-oidc"
  service_account_id = google_service_account.api.id
  github_repository  = "mblasi/training"
}

# Cloud Run module
module "cloudrun" {
  source = "../../modules/cloudrun"

  project_id                 = var.project_id
  region                     = var.region
  service_name               = "api"
  image                      = "us-central1-docker.pkg.dev/${var.project_id}/trainia/api:${var.image_tag}"
  database_url_secret_name   = module.secrets.database_url_secret_name
  firebase_project_id        = var.project_id
  admin_emails               = ""
  cloud_sql_connection_name  = module.cloudsql.instance_connection_name
  domain                     = "api.staging.trainia.blasi.ar"
}
