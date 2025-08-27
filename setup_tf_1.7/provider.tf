# provider.tf

terraform {
  required_providers {
    vastdata = {
      source  = "vast-data/vastdata"
      version = ">= 1.7.0"
    }
    local = {
      source  = "hashicorp/local"
      version = "~> 2.5"
    }
  }
}

provider "vastdata" {
  # VAST Management Server (VMS) endpoint and credentials.
  # These are sourced from the variables defined in variables.tf.
  # It is recommended to set these using environment variables for security.
  # Example: export TF_VAR_vast_user='admin'

  host            = var.vast_host
  port            = var.vast_port
  username        = var.vast_user
  password        = var.vast_password

  # Set to true if your VMS uses a self-signed certificate
  skip_ssl_verify = true
}

provider "local" {
  # This provider is used to write connection details to a local file.
}
