# user.tf - v3.0 Pure HTTP approach for UID discovery

# Get existing users via HTTP API for UID discovery
data "http" "existing_users" {
  count  = var.user_context == "local" ? 1 : 0
  url    = "https://${var.vast_host}:${var.vast_port}/api/v5/users/"
  method = "GET"
  
  request_headers = {
    "Accept"        = "application/json"
    "Content-Type"  = "application/json"
    "Authorization" = "Basic ${base64encode("${var.vast_user}:${var.vast_password}")}"
  }
  
  # Skip SSL verification (as done in provider.tf)
  insecure = true
  
  lifecycle {
    postcondition {
      condition     = self.status_code == 200
      error_message = "Failed to fetch users from VastData API. Status: ${self.status_code}"
    }
  }
}

# Process the users response to find available UID
locals {
  # Parse existing users JSON response
  existing_users_json = var.user_context == "local" ? jsondecode(data.http.existing_users[0].response_body) : []
  
  # Extract existing UIDs from the response
  existing_uids = var.user_context == "local" ? [
    for user in local.existing_users_json :
    user.uid if can(user.uid) && user.uid != null
  ] : []
  
  # Define UID range 
  min_uid = 5000
  max_uid = 9999
  
  # Ultra-simple deterministic UID generation
  # Use string lengths and a simple formula for deterministic results
  username_length = length(var.user_name)
  tenant_length = length(var.tenant_name)
  
  # Create a simple deterministic number based on string properties
  # This ensures same username+tenant always gets same UID (if available)
  base_number = (local.username_length * 137) + (local.tenant_length * 73) + 5000
  
  # Map to UID range
  uid_range = local.max_uid - local.min_uid + 1  
  hash_uid = local.min_uid + (local.base_number % local.uid_range)
  
  # Check if hash UID is available
  hash_uid_available = var.user_context == "local" ? !contains(local.existing_uids, local.hash_uid) : false
  
  # For sequential search, we'll try a few common UIDs instead of generating full range
  # This is much more efficient and practical
  candidate_uids = [
    local.hash_uid,                    # Try our hash UID first
    local.min_uid,                     # Try start of range
    local.min_uid + 1,                 # Try next few
    local.min_uid + 2,
    local.min_uid + 3,
    local.min_uid + 5,
    local.min_uid + 7,
    local.min_uid + 11,
    local.min_uid + 13,
    local.min_uid + 17,
    local.min_uid + 19,
    local.min_uid + 23,
    local.min_uid + 29,
    local.min_uid + 31,
    local.min_uid + 37,
    local.min_uid + 41,
    local.min_uid + 43,
    local.min_uid + 47,
    local.min_uid + 53,
    local.min_uid + 59,
    local.min_uid + 61,
    local.min_uid + 67,
    local.min_uid + 71,
    local.min_uid + 73,
    local.min_uid + 79,
    local.min_uid + 83,
    local.min_uid + 89,
    local.min_uid + 97
  ]
  
  # Find first available UID from candidates
  available_sequential_uid = var.user_context == "local" && !local.hash_uid_available ? [
    for uid in local.candidate_uids :
    uid if !contains(local.existing_uids, uid) && uid <= local.max_uid
  ][0] : null
  
  # Final UID to use
  discovered_uid = var.user_context == "local" ? (
    local.hash_uid_available ? local.hash_uid : local.available_sequential_uid
  ) : null
  
  # Discovery method for reporting
  uid_discovery_method = var.user_context == "local" ? (
    local.hash_uid_available ? "hash" : "sequential"
  ) : null
}

# Validation to ensure we found a UID
resource "null_resource" "validate_uid" {
  count = var.user_context == "local" ? 1 : 0
  
  lifecycle {
    precondition {
      condition = local.discovered_uid != null
      error_message = <<-EOT
        No available UID found from candidate list.
        
        Tried ${length(local.candidate_uids)} candidate UIDs in range ${local.min_uid}-${local.max_uid}.
        Found ${length(local.existing_uids)} existing UIDs: ${jsonencode(local.existing_uids)}
        
        Candidates tried: ${jsonencode(local.candidate_uids)}
        
        Consider:
        1. Expanding the candidate list in user.tf
        2. Using a different UID range
        3. Cleaning up unused users in VastData
      EOT
    }
  }
}

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

# Create local user with HTTP-discovered UID
resource "vastdata_user" "create_local_user" {
  count = var.user_context == "local" ? 1 : 0
  name  = var.user_name
  uid   = local.discovered_uid
  
  depends_on = [
    null_resource.validate_uid,
    data.http.existing_users
  ]
  
  lifecycle {
    ignore_changes = [uid]
  }
}

# Create access key for local user
resource "vastdata_user_key" "local_demo_key" {
  count     = var.user_context == "local" ? 1 : 0
  user_id   = vastdata_user.create_local_user[0].id
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
  
  # Get the username
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