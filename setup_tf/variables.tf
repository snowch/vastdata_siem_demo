# variables.tf - v2.0 complete

variable "vast_host" {
  type        = string
  description = "The IP address or hostname of the VAST Management Server (VMS)."
}

variable "vast_port" {
  type        = number
  description = "The port of the VAST Management Server (VMS)."
}

variable "vast_user" {
  type        = string
  description = "The username for VMS authentication."
  sensitive   = true
}

variable "vast_password" {
  type        = string
  description = "The password for VMS authentication."
  sensitive   = true
}

variable "tenant_name" {
  type        = string
  description = "The Tenant Name."
}

variable "user_name" {
  type        = string
  description = "The User Name."
}

variable "user_context" {
  type        = string
  description = "The User Context (local, ad, nis, or ldap)."
  validation {
    condition     = contains(["local", "ad", "nis", "ldap"], var.user_context)
    error_message = "User context must be one of: local, ad, nis, ldap."
  }
}

# Variables referenced in terraform.tfvars to avoid warnings
variable "enable_user_fallback" {
  type        = bool
  description = "Enable fallback to local user if external user lookup fails."
  default     = true
}

variable "create_local_user_if_ad_missing" {
  type        = bool
  description = "Create a local user if the external user is not found."
  default     = true
}

variable "local_user_password" {
  type        = string
  description = "Password for local user. Set to null to auto-generate."
  default     = null
  sensitive   = true
}

variable "database_view_name" {
  type        = string
  description = "The name of the database (bucket)."
}

variable "database_view_path" {
  type        = string
  description = "The path for the new database view."
}

variable "s3_view_name" {
  type        = string
  description = "The name of the s3 bucket."
}

variable "s3_view_path" {
  type        = string
  description = "The path for the s3 view."
}

variable "kafka_view_name" {
  type        = string
  description = "The name of the kafka bucket."
}

variable "kafka_view_path" {
  type        = string
  description = "The path for the kafka view."
}

variable "vip_pool_name" {
  type        = string
  description = "The name for the vip pool."
}

variable "vip_pool_start_ip" {
  type        = string
  description = "The start IP for the vip pool."
}

variable "vip_pool_end_ip" {
  type        = string
  description = "The end IP for the vip pool."
}

variable "vip_pool_subnet_cidr" {
  type        = string
  description = "The subnet cidr for the vip pool."
}