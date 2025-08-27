# provider.tf - VastData Provider v2.0

terraform {
  required_providers {
    vastdata = {
      source  = "vast-data/vastdata"
      version = ">= 2.0.0"
    }
    local = {
      source  = "hashicorp/local"
      version = "~> 2.5"
    }
  }
}

provider "vastdata" {
  host            = var.vast_host
  port            = var.vast_port
  username        = var.vast_user
  password        = var.vast_password
  skip_ssl_verify = true
}

provider "local" {
  # This provider is used to write connection details to a local file.
}