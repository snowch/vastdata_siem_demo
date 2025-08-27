# user.tf - v2.0 with local/external user support

# Try to get external user (AD/LDAP/NIS) - conditional on user_context
data "vastdata_non_local_user" "the_user" {
  count     = var.user_context != "local" ? 1 : 0
  username  = var.user_name
  context   = var.user_context
  tenant_id = data.vastdata_tenant.the_tenant.id
}

# Create access key for external user
resource "vastdata_non_local_user_key" "demo_key" {
  count     = var.user_context != "local" && length(data.vastdata_non_local_user.the_user) > 0 ? 1 : 0
  uid       = data.vastdata_non_local_user.the_user[0].uid
  tenant_id = data.vastdata_tenant.the_tenant.id
  enabled   = true
}

# Get local user (assumes user exists in VAST - create via UI first)
data "vastdata_user" "local_user" {
  count     = var.user_context == "local" ? 1 : 0
  username  = var.user_name
  tenant_id = data.vastdata_tenant.the_tenant.id
}

# Create access key for local user
resource "vastdata_user_key" "local_demo_key" {
  count     = var.user_context == "local" && length(data.vastdata_user.local_user) > 0 ? 1 : 0
  uid       = data.vastdata_user.local_user[0].uid
  tenant_id = data.vastdata_tenant.the_tenant.id
  enabled   = true
}

# Locals for determining which user/keys to use
locals {
  # Determine if we're using external user
  using_external_user = var.user_context != "local" && length(data.vastdata_non_local_user.the_user) > 0
  
  # Determine if we're using local user
  using_local_user = var.user_context == "local" && length(data.vastdata_user.local_user) > 0
  
  # Get the username
  username = local.using_external_user ? data.vastdata_non_local_user.the_user[0].username : (
    local.using_local_user ? data.vastdata_user.local_user[0].username : var.user_name
  )
  
  # Get the access key
  access_key = local.using_external_user ? vastdata_non_local_user_key.demo_key[0].access_key : (
    local.using_local_user ? vastdata_user_key.local_demo_key[0].access_key : ""
  )
  
  # Get the secret key
  secret_key = local.using_external_user ? vastdata_non_local_user_key.demo_key[0].secret_key : (
    local.using_local_user ? vastdata_user_key.local_demo_key[0].secret_key : ""
  )
}