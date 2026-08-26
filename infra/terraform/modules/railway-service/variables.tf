variable "service_name" {
  type        = string
  description = "Must match the service's existing Railway service name exactly."
}

variable "railway_project_id" {
  type        = string
  description = "The Railway project this service belongs to."
}

variable "source_repo" {
  type        = string
  description = "e.g. \"s091648/scrape-and-analyze\" or \"s091648/chatbot-plugin\" per Constitution Principle V's two-repo split. Actual deploys still happen via `railway up` (CLI push, not git-integration auto-deploy per Principle V) — this is registration metadata, not a build trigger."
}

variable "source_repo_branch" {
  type        = string
  description = "Required by the provider when source_repo is set, but not exposed by Railway's read API (no active git-integration trigger to verify against — Principle V). Always \"master\": this module is only ever instantiated in environments/production, which always deploys from master."
  default     = "master"
}

variable "root_directory" {
  type        = string
  description = "Subdirectory within source_repo this service builds from (e.g. \"/frontend\"), or \"/\" for the monorepo root. null for chatbot-plugin (its own separate repo)."
  default     = "/"
}

variable "cron_schedule" {
  type        = string
  description = "Production's real cron schedule for scheduled services (null for non-cron services). Omitting this for a service that actually has one would make Terraform try to UNSET it on apply — discovered the hard way via terraform plan, not guessed up front."
  default     = null
}
