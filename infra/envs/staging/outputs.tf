# Outputs for staging environment

output "api_url" {
  description = "URL of the Cloud Run API service"
  value       = module.cloudrun.service_url
}

output "cloudsql_connection_name" {
  description = "Cloud SQL instance connection name"
  value       = module.cloudsql.instance_connection_name
}

output "database_name" {
  description = "Database name"
  value       = module.cloudsql.database_name
}

output "database_user" {
  description = "Database user"
  value       = module.cloudsql.database_user
}

output "database_password" {
  description = "Database password (sensitive)"
  value       = module.cloudsql.database_password
  sensitive   = true
}

output "wif_pool_name" {
  description = "Workload Identity Pool name"
  value       = module.wif.pool_name
}

output "wif_provider_name" {
  description = "Workload Identity Pool Provider name"
  value       = module.wif.provider_name
}
