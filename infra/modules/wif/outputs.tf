# Outputs for Workload Identity Federation module

output "pool_name" {
  description = "Full name of the Workload Identity Pool"
  value       = google_iam_workload_identity_pool.github.name
}

output "provider_name" {
  description = "Full name of the Workload Identity Pool Provider"
  value       = google_iam_workload_identity_pool_provider.github.name
}
