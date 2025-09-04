# provider.tf - VastData Provider v4.0 with Kafka provider

terraform {
  required_providers {
    vastdata = {
      source  = "vast-data/vastdata"
      version = ">= 2.0.0"
    }
    kafka = {
      source  = "Mongey/kafka"
      version = ">= 0.7.0"
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

provider "kafka" {
  bootstrap_servers = ["${local.kafka_broker_ip}:9092"]
  tls_enabled = false  # Set to true if using TLS
  skip_tls_verify = true  # Only for development/testing
}

provider "local" {
  # This provider is used to write connection details to a local file.
}

provider "http" {
  # This provider is used for HTTP API calls to VastData for UID discovery.
}

provider "null" {
  # This provider is used for validation and lifecycle management.
}