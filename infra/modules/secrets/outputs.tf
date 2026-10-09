# Outputs for Secret Manager module

output "database_url_secret_id" {
  description = "Secret ID for database URL"
  value       = google_secret_manager_secret.database_url.secret_id
}

output "database_url_secret_name" {
  description = "Full resource name of database URL secret"
  value       = google_secret_manager_secret.database_url.name
}
