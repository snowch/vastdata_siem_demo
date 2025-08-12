#!/usr/bin/env bash

# Change to the script's directory
cd "$(dirname "$0")"

# Define the variables file name
TFVARS_FILE="terraform.tfvars"

# Define the Terraform Docker image to use
TERRAFORM_IMAGE="hashicorp/terraform:1.13.0-rc1"

# Run 'terraform' using the official Docker image
echo "Running terraform apply inside a Docker container..."
sudo docker run --rm -it \
  -v "$(pwd):/app" \
  -w "/app" \
  "$TERRAFORM_IMAGE" "$@" 
  
  # -var-file="terraform.tfvars"
