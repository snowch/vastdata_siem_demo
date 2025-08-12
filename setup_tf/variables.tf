# variables.tf

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

variable "database_owner" {
  type        = string
  description = "The name of the user to be created as the database owner."
  default     = "demo-owner"
}

variable "database_name" {
  type        = string
  description = "The name of the database (and bucket)."
  default     = "demo-database"
}

variable "database_view_path" {
  type        = string
  description = "The path for the new view."
  default     = "/demo-view"
}
