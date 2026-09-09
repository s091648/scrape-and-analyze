# Single flat root config (specs/025-iac-provisioning). Applied once per
# environment against its own HCP Terraform workspace; the environment is
# selected at runtime via TF_WORKSPACE (see backend.tf) + a secrets/<env>.tfvars
# overlay, never by a second copy of these files.
#
# Scope: GitHub Actions secrets/variables only (github-ci.tf). Railway service
# variables are NOT Terraform-managed — the Railway half moved to .railway/railway.ts + `railway config` (Revision 6); the
# community railway provider used before that was unreliable at this scale (see
# .railway/README.md).
terraform {
  required_version = ">= 1.9"

  required_providers {
    github = {
      source  = "integrations/github"
      version = "~> 6.0"
    }
  }
}
