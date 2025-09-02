# vip.tf - v6.0 Main pool for database, auto-discovered new pool for Kafka

# Get VIP pools via HTTP API
data "http" "vip_pools" {
  url    = "https://${var.vast_host}:${var.vast_port}/api/v5/vippools/"
  method = "GET"
  
  request_headers = {
    "Accept"        = "application/json"
    "Content-Type"  = "application/json"
    "Authorization" = "Basic ${base64encode("${var.vast_user}:${var.vast_password}")}"
  }
  
  insecure = true
  
  lifecycle {
    postcondition {
      condition     = self.status_code == 200
      error_message = "Failed to fetch VIP pools from VastData API. Status: ${self.status_code}"
    }
  }
}

# Process VIP pools response
locals {
  # Parse VIP pools JSON response
  vip_pools_json = jsondecode(data.http.vip_pools.response_body)
  
  # Find the main VIP pool
  main_vip_pool = [
    for pool in local.vip_pools_json :
    pool if pool.name == "main"
  ][0]
  
  # Extract subnet CIDR from main pool (reuse for new Kafka pool)
  main_pool_subnet_cidr = local.main_vip_pool.subnet_cidr
  
  # Extract IP ranges from main pool for database endpoints
  main_pool_ranges = local.main_vip_pool.ip_ranges
  first_range = local.main_pool_ranges[0]
  first_range_start = local.first_range[0]
  first_range_end = local.first_range[1]
  
  # Parse IP addresses for database endpoints (consecutive IPs)
  start_ip_octets = split(".", local.first_range_start)
  start_ip_last_octet = tonumber(local.start_ip_octets[3])
  start_ip_base = "${local.start_ip_octets[0]}.${local.start_ip_octets[1]}.${local.start_ip_octets[2]}"
  
  # Database endpoints from main pool
  database_ip_1 = "${local.start_ip_base}.${local.start_ip_last_octet}"
  database_ip_2 = "${local.start_ip_base}.${local.start_ip_last_octet + 1}"
  
  # Validate database IPs
  end_ip_octets = split(".", local.first_range_end)
  end_ip_last_octet = tonumber(local.end_ip_octets[3])
  consecutive_ips_valid = (local.start_ip_last_octet + 1) <= local.end_ip_last_octet
  
  # Collect all existing IP ranges from all VIP pools to avoid conflicts
  all_existing_ranges = flatten([
    for pool in local.vip_pools_json : pool.ip_ranges
  ])
  
  # Find available IP range for new Kafka VIP pool
  # Use same subnet as main pool but different IP range
  
  # Calculate a new IP range that doesn't conflict with existing ones
  # Strategy: Look for available range in same subnet
  
  # Parse main pool subnet to understand the network
  main_subnet_octets = split(".", local.start_ip_base)
  base_network = "${local.main_subnet_octets[0]}.${local.main_subnet_octets[1]}.${local.main_subnet_octets[2]}"
  
  # Find next available range - try different starting points
  kafka_range_candidates = [
    ["${local.base_network}.220", "${local.base_network}.222"],  # Try .220-.222
    ["${local.base_network}.230", "${local.base_network}.232"],  # Try .230-.232  
    ["${local.base_network}.240", "${local.base_network}.242"],  # Try .240-.242
    ["${local.base_network}.250", "${local.base_network}.252"],  # Try .250-.252
  ]
  
  # Check which candidate doesn't conflict with existing ranges
  kafka_range_available = [
    for candidate in local.kafka_range_candidates :
    candidate if !contains([for range in local.all_existing_ranges : range], candidate)
  ][0]  # Take first available
}

# Validation for database IPs
resource "null_resource" "validate_vip_ips" {
  lifecycle {
    precondition {
      condition = local.consecutive_ips_valid
      error_message = <<-EOT
        Unable to find two consecutive IP addresses in main VIP pool range.
        
        Pool range: ${local.first_range_start} - ${local.first_range_end}
        Attempted IPs: ${local.database_ip_1}, ${local.database_ip_2}
      EOT
    }
  }
}

# Validation for Kafka pool range
resource "null_resource" "validate_kafka_range" {
  lifecycle {
    precondition {
      condition = local.kafka_range_available != null
      error_message = <<-EOT
        Unable to find available IP range for Kafka VIP pool.
        
        Tried candidates: ${jsonencode(local.kafka_range_candidates)}
        Existing ranges: ${jsonencode(local.all_existing_ranges)}
        
        Consider manually specifying a different IP range or expanding available ranges.
      EOT
    }
  }
}

# Reference to main VIP pool (for database and S3)
data "vastdata_vip_pool" "main" {
  name = "main"
}

# Create new VIP pool for Kafka with auto-discovered settings
resource "vastdata_vip_pool" "kafka_pool" {
  name        = var.vip_pool_name
  role        = "PROTOCOLS"
  subnet_cidr = local.main_pool_subnet_cidr     # Auto-discovered from main pool
  ip_ranges   = [local.kafka_range_available]   # Auto-discovered available range
  
  depends_on = [
    null_resource.validate_vip_ips,
    null_resource.validate_kafka_range
  ]
}