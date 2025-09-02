# user.tf - v2.1 with corrected user creation and lookup

# Try to get external user (AD/LDAP/NIS)
data "vastdata_nonlocal_user" "the_user" {
  count     = var.user_context != "local" ? 1 : 0
  username  = var.user_name
  context   = var.user_context
  tenant_id = data.vastdata_tenant.the_tenant.id
}

# Create access key for external user
resource "vastdata_nonlocal_user_key" "demo_key" {
  count     = var.user_context != "local" && length(data.vastdata_nonlocal_user.the_user) > 0 ? 1 : 0
  uid       = data.vastdata_nonlocal_user.the_user[0].uid
  tenant_id = data.vastdata_tenant.the_tenant.id
  enabled   = true
}

# Create local user - minimal arguments only
resource "vastdata_user" "create_local_user" {
  count = var.user_context == "local" ? 1 : 0
  name  = var.user_name
  # Only name is supported - tenant_id, password, enabled are not supported
}

# Create access key for local user - directly reference the created user
resource "vastdata_user_key" "local_demo_key" {
  count     = var.user_context == "local" ? 1 : 0
  user_id   = vastdata_user.create_local_user[0].id  # Direct reference to created user
  tenant_id = data.vastdata_tenant.the_tenant.id
  enabled   = true
  
  depends_on = [vastdata_user.create_local_user]
}

# Locals for determining which user/keys to use
locals {
  # Determine if we're using external user
  using_external_user = var.user_context != "local" && length(data.vastdata_nonlocal_user.the_user) > 0
  
  # Determine if we're using local user
  using_local_user = var.user_context == "local"
  
  # Get the username - use the created user's name for local users
  username = local.using_external_user ? data.vastdata_nonlocal_user.the_user[0].username : (
    local.using_local_user ? vastdata_user.create_local_user[0].name : var.user_name
  )
  
  # Get the user ID
  user_id = local.using_external_user ? data.vastdata_nonlocal_user.the_user[0].uid : (
    local.using_local_user ? vastdata_user.create_local_user[0].id : null
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