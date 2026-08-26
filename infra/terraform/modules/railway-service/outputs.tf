output "railway_service_id" {
  value       = railway_service.this.id
  description = "Consumed cross-workspace by environments/staging/main.tf via terraform_remote_state, since railway_service is only ever declared here (production) — research.md §9."
}
