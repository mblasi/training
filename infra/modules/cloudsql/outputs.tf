# Outputs for Cloud SQL module

output "instance_name" {
  value       = google_sql_database_instance.main.name
  description = "Cloud SQL instance name"
}

output "instance_connection_name" {
  value       = google_sql_database_instance.main.connection_name
  description = "Cloud SQL instance connection name (for Unix socket connection)"
}

output "database_name" {
  value       = google_sql_database.main.name
  description = "Database name"
}

output "database_user" {
  value       = google_sql_user.main.name
  description = "Database user"
}

output "database_password" {
  value       = random_password.db_password.result
  description = "Database password"
  sensitive   = true
}
