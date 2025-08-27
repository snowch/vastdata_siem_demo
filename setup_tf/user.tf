# user.tf - v2.0 with corrected syntax

# Try to get external user (AD/LDAP/NIS) - corrected data source name
data "vastdata_nonlocal_user" "the_user" {
  count     = var.user_context != "local" ? 1 : 0
  username  = var.user_name
  context   = var.user_context
  tenant_id = data.vastdata_tenant.the_tenant.id
}

# Create access key for external user
resource "vastdata_nonlocal_user_key" "demo_key" {
  count     = var.user_context != "local" && length(data.vastdata_nonlocal_user.the_user) > 0 ? 1 : 0
  uid       = data.vastdata_nonlocal_user.the_user[0].uid  # Back to uid parameter
  tenant_id = data.vastdata_tenant.the_tenant.id
  enabled   = true
}

# Create local user if it doesn't exist - minimal arguments
resource "vastdata_user" "create_local_user" {
  count = var.user_context == "local" && var.create_local_user_if_ad_missing ? 1 : 0
  name  = var.user_name
  # Only use supported arguments - removed password, tenant_id, enabled
}

# Get local user (either existing or newly created)
data "vastdata_user" "local_user" {
  count      = var.user_context == "local" ? 1 : 0
  name       = var.user_name
  depends_on = [vastdata_user.create_local_user]  # Ensure creation happens first
}

# Create access key for local user
resource "vastdata_user_key" "local_demo_key" {
  count     = var.user_context == "local" ? 1 : 0
  user_id   = var.user_context == "local" ? (
    length(data.vastdata_user.local_user) > 0 ? data.vastdata_user.local_user[0].id : vastdata_user.create_local_user[0].id
  ) : null
  tenant_id = data.vastdata_tenant.the_tenant.id
  enabled   = true
}

# Locals for determining which user/keys to use
locals {
  # Determine if we're using external user
  using_external_user = var.user_context != "local" && length(data.vastdata_nonlocal_user.the_user) > 0
  
  # Determine if we're using local user (either existing data source or created resource)
  using_local_user = var.user_context == "local"
  
  # Get the username
  username = local.using_external_user ? data.vastdata_nonlocal_user.the_user[0].username : (
    local.using_local_user ? var.user_name : var.user_name  # Use var.user_name for local users
  )
  
  # Get the access key
  access_key = local.using_external_user ? vastdata_nonlocal_user_key.demo_key[0].access_key : (
    local.using_local_user ? vastdata_user_key.local_demo_key[0].access_key : ""
  )
  
  # Get the secret key
  secret_key = local.using_external_user ? vastdata_nonlocal_user_key.demo_key[0].secret_key : (
    local.using_local_user ? vastdata_user_key.local_demo_key[0].secret_key : ""
  )
}