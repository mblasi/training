terraform {
  required_version = ">= 1.8.0"
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 6.0"
    }
    random = {
      source  = "hashicorp/random"
      version = "~> 3.6"
    }
  }
}

# Cloud SQL instance (PostgreSQL 16)
resource "google_sql_database_instance" "main" {
  name             = var.instance_name
  project          = var.project_id
  region           = var.region
  database_version = "POSTGRES_16"

  settings {
    tier = var.tier

    ip_configuration {
      ipv4_enabled    = false
      private_network = null
    }

    backup_configuration {
      enabled = false
    }

    availability_type = "ZONAL"
  }

  deletion_protection = false
}

# Database
resource "google_sql_database" "main" {
  name     = var.database_name
  project  = var.project_id
  instance = google_sql_database_instance.main.name
}

# Database user
resource "google_sql_user" "main" {
  name     = "trainia"
  project  = var.project_id
  instance = google_sql_database_instance.main.name
  password = random_password.db_password.result
}

# Generate random password for database user
resource "random_password" "db_password" {
  length  = 32
  special = true
}

# IAM binding for Cloud Run service account to connect via Cloud SQL Auth Proxy
resource "google_project_iam_member" "cloudsql_client" {
  project = var.project_id
  role    = "roles/cloudsql.client"
  member  = "serviceAccount:${var.service_account_email}"
}
