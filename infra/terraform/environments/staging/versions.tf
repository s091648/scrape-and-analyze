# Kept identical to ../production/versions.tf — Terraform requires a full
# `terraform {}` block (required_version + required_providers) per root
# module, so this can't literally be a single shared top-level file the way
# plan.md's illustrative tree suggests. The `cloud {}` workspace binding
# lives separately in backend.tf so this file's provider pins stay a clean,
# diffable copy of each other.
terraform {
  required_version = ">= 1.9"

  required_providers {
    railway = {
      source  = "terraform-community-providers/railway"
      version = "~> 0.6"
    }
    github = {
      source  = "integrations/github"
      version = "~> 6.0"
    }
  }
}
