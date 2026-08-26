# IMPORTANT (research.md §9): the railway_service Terraform resource reads/
# writes exactly ONE ServiceInstance — the project's primary environment
# (production, for this project) — regardless of what environment_id you
# might wish it applied to. Railway's own API is genuinely per-environment
# (ServiceInstanceUpdateInput takes cronSchedule/source/rootDirectory per
# environment — confirmed via introspection, and this project's real cron
# schedules do differ between staging/production), but this provider's
# resource does not expose that. Declaring this resource in BOTH staging's
# and production's Terraform state would make both workspaces fight over
# the same single underlying object.
#
# Fix: this module is instantiated exactly ONCE per service, from
# environments/production/main.tf only (see that file). Staging never
# declares railway_service at all — it only declares railway_variable
# (module.railway-variables), referencing this module's `id` output via
# terraform_remote_state (see environments/staging/main.tf).
# `regions` is deliberately left undeclared here — this provider has a known,
# unresolved bug when setting it (a "Value Conversion Error: Received unknown
# value" panic; see terraform-community-providers/terraform-provider-railway
# issues #35/#49, research.md §9).
#
# `source_repo_branch` is required by the provider schema but not exposed by
# Railway's read API at all (no active git-integration trigger to compare
# against — Principle V's CLI-push deploy model), so import always comes back
# with it unset, and any declared value would show a perpetual, apply-only-
# once diff for a field that has no functional effect on how these services
# actually deploy.
#
# Both are ignored so `terraform plan` reflects real, meaningful drift only —
# not provider quirks this project has no way to cleanly resolve.
resource "railway_service" "this" {
  name               = var.service_name
  project_id         = var.railway_project_id
  source_repo        = var.source_repo
  source_repo_branch = var.source_repo_branch
  root_directory     = var.root_directory
  cron_schedule      = var.cron_schedule

  lifecycle {
    ignore_changes = [regions, source_repo_branch]
  }
}
