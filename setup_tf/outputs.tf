# outputs.tf - v2.0 with user creation support

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

output "user_authentication_method" {
  description = "Shows whether external, existing local, or newly created local user was used."
  value = local.using_external_user ? "external" : (
    var.user_context == "local" ? (
      length(vastdata_user.create_local_user) > 0 ? "local_created" : "local_existing"
    ) : "none"
  )
}