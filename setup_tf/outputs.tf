# outputs.tf - v2.1 with debugging information

output "s3_access_key" {
  description = "The S3 access key for the demo user."
  value       = local.access_key
}

output "s3_secret_key" {
  description = "The S3 secret key for the demo user."
  value       = local.secret_key
  sensitive   = true
}

output "connection_details_file" {
  description = "Path to the file containing connection details."
  value       = local_file.connection_details.filename
}

output "user_type" {
  description = "The type of user being used."
  value       = var.user_context
}

output "username" {
  description = "The actual username being used."
  value       = local.username
}

output "user_id" {
  description = "The user ID being used."
  value       = local.user_id
}

output "tenant_id" {
  description = "The tenant ID being used."
  value       = data.vastdata_tenant.the_tenant.id
}

# Debug outputs to verify user creation
output "debug_created_user_name" {
  description = "Name of the created local user (if any)."
  value       = length(vastdata_user.create_local_user) > 0 ? vastdata_user.create_local_user[0].name : "none"
}

output "debug_created_user_id" {
  description = "ID of the created local user (if any)."
  value       = length(vastdata_user.create_local_user) > 0 ? vastdata_user.create_local_user[0].id : "none"
}

output "debug_using_local_user" {
  description = "Are we using local user?"
  value       = local.using_local_user
}