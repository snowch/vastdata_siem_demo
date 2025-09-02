# outputs.tf - v3.0 with HTTP-based UID discovery information

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

# HTTP-based UID discovery outputs
output "discovered_uid" {
  description = "The UID that was discovered via HTTP API for local user (if applicable)."
  value       = var.user_context == "local" ? local.discovered_uid : null
}

output "uid_discovery_method" {
  description = "The method used to discover the UID (hash or sequential)."
  value       = var.user_context == "local" ? local.uid_discovery_method : null
}

output "uid_discovery_info" {
  description = "Detailed information about HTTP-based UID discovery."
  value = var.user_context == "local" ? {
    discovered_uid        = local.discovered_uid
    method               = local.uid_discovery_method
    attempted_hash_uid   = local.hash_uid
    hash_uid_available   = local.hash_uid_available
    total_existing       = length(local.existing_uids)
    existing_uids        = local.existing_uids
    uid_range           = "${local.min_uid}-${local.max_uid}"
    username_length     = length(var.user_name)
    tenant_length       = length(var.tenant_name)
    base_calculation    = "(${length(var.user_name)} * 137) + (${length(var.tenant_name)} * 73) + 5000"
    candidates_tried    = length(local.candidate_uids)
    candidate_uids      = local.candidate_uids
  } : null
}

output "api_debug_info" {
  description = "Debug information about the VastData API call (for troubleshooting)."
  value = var.user_context == "local" ? {
    api_url         = data.http.existing_users[0].url
    response_status = data.http.existing_users[0].status_code
    users_found     = length(local.existing_users_json)
  } : null
}