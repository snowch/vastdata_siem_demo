# outputs.tf

# output "vast_host" {
#   description = "The VAST VMS host."
#   value       = var.vast_host
# }
# 
# output "vast_port" {
#   description = "The VAST VMS port."
#   value       = var.vast_port
# }
# 
# output "vast_user" {
#   description = "The VAST VMS username."
#   value       = var.vast_user
#   sensitive   = true
# }
# 
# output "vast_password" {
#   description = "The VAST VMS password."
#   value       = var.vast_password
#   sensitive   = true
# }

output "s3_access_key" {
  description = "The S3 access key for the demo user."
  value       = vastdata_user_key.demo_key.access_key
}

output "s3_secret_key" {
  description = "The S3 secret key for the demo user."
  value       = vastdata_user_key.demo_key.secret_key
  sensitive   = true
}

output "connection_details_file" {
  description = "Path to the file containing connection details."
  value       = local_file.connection_details.filename
}
