# Kept identical to ../staging/versions.tf — see that file's header comment
# for why this is duplicated per environment rather than a single shared file.
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
