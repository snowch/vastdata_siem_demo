# provider.tf - VastData Provider v5.0 without Kafka provider (using Docker instead)

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
    http = {
      source  = "hashicorp/http"
      version = "~> 3.4"
    }
    null = {
      source  = "hashicorp/null"
      version = "~> 3.2"
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

provider "http" {
  # This provider is used for HTTP API calls to VastData for UID discovery.
}

provider "null" {
  # This provider is used for validation, lifecycle management, and Docker commands.
}