terraform {
  cloud {
    organization = "scrape-analyzer"

    workspaces {
      name = "scrape-analyzer-production"
    }
  }
}
