terraform {
  required_version = ">= 1.13.5, < 2.0"

  # Separate state from infra/ (AWS): its own HCP Terraform workspace, so one plan
  # can never touch both clouds. `terraform init -backend=false` skips this block.
  cloud {
    organization = "ooad-kremeriatko8"
    workspaces {
      name = "peach-gcp"
    }
  }

  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 7.10"
    }
    random = {
      source  = "hashicorp/random"
      version = "~> 3.7"
    }
  }
}

# No credentials here and no service account key anywhere. Locally Terraform uses
# application default credentials (`gcloud auth application-default login`);
# in HCP Terraform it uses Workload Identity Federation (dynamic credentials).
provider "google" {
  project = var.project_id
  region  = var.region
}
