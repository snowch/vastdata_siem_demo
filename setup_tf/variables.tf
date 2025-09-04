# variables.tf - v5.0 with Kafka topics configuration

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

# Database and S3 view configuration
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

# Kafka configuration
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

# Kafka topics configuration
variable "kafka_zeek_topic" {
  type        = string
  description = "The name of the Kafka topic for Zeek SIEM logs."
  default     = "siem_zeek_live_logs"
}

variable "kafka_event_log_topic" {
  type        = string
  description = "The name of the Kafka topic for Fluentd event logs."
  default     = "siem_fluentd_events"
}

variable "kafka_topic_partitions" {
  type        = number
  description = "Number of partitions for Kafka topics."
  default     = 3
}

variable "kafka_topic_replication_factor" {
  type        = number
  description = "Replication factor for Kafka topics."
  default     = 1
}

# Manual override options for Kafka VIP pool range (only used if auto-discovery fails)
variable "kafka_vip_pool_range_start" {
  type        = string
  description = "Manual override: Start IP for Kafka VIP pool (only used if auto-discovery fails)."
  default     = null
  validation {
    condition = var.kafka_vip_pool_range_start == null || can(regex("^(?:[0-9]{1,3}\\.){3}[0-9]{1,3}$", var.kafka_vip_pool_range_start))
    error_message = "kafka_vip_pool_range_start must be a valid IP address or null."
  }
}

variable "kafka_vip_pool_range_end" {
  type        = string
  description = "Manual override: End IP for Kafka VIP pool (only used if auto-discovery fails)."
  default     = null
  validation {
    condition = var.kafka_vip_pool_range_end == null || can(regex("^(?:[0-9]{1,3}\\.){3}[0-9]{1,3}$", var.kafka_vip_pool_range_end))
    error_message = "kafka_vip_pool_range_end must be a valid IP address or null."
  }
}