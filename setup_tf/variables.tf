# variables.tf - v3.0 Clean HTTP approach (no external dependencies)

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

# Note: No UID variables needed - automatically discovered via HTTP API!

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

variable "kafka_vip_pool_name" {
  type        = string
  description = "The name for the new Kafka VIP pool."
}

# Note: VIP pool IP ranges and subnet CIDR auto-discovered from main pool!
