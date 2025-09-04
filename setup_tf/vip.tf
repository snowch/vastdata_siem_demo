# vip.tf - v11.0 Clean dynamic discovery with Kafka broker IP

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
  
  # REAL CONFLICT DETECTION: 
  # Use the main pool's network (we know it's valid) and scan for conflicts
  network_base = local.start_ip_base  # Reliable - taken from working main pool
  
  # Collect ALL used IP addresses from ALL existing VIP pools
  # Handle different possible ip_ranges formats from the API
  all_existing_ranges = flatten([
    for pool in local.vip_pools_json : 
    try(pool.ip_ranges, []) if can(pool.ip_ranges)
  ])
  
  # Debug: Let's see what the ip_ranges structure actually looks like
  # by using the first range from main pool as reference
  main_pool_range_sample = try(local.main_vip_pool.ip_ranges[0], null)
  
  # Parse IP ranges more defensively - handle different possible formats
  used_ip_numbers = toset(flatten([
    for range_item in local.all_existing_ranges : 
    # Handle case where range_item might be an array [start_ip, end_ip]
    try([
      for i in range(
        tonumber(split(".", try(range_item[0], range_item.start_ip))[3]), 
        tonumber(split(".", try(range_item[1], range_item.end_ip))[3]) + 1
      ) : i
    ], 
    # Fallback: try object properties if array indexing fails
    try([
      for i in range(
        tonumber(split(".", range_item.start_ip)[3]), 
        tonumber(split(".", range_item.end_ip)[3]) + 1
      ) : i
    ], []))  # Empty array if both attempts fail
  ]))
  
  # Find first available 3-consecutive-IP block
  # Scan reasonable range (avoiding very low/high numbers)
  scan_candidates = [
    for start_octet in range(50, 240) : {
      start_ip = start_octet
      end_ip   = start_octet + 2  # 3 IPs total
      is_available = !contains(local.used_ip_numbers, start_octet) && !contains(local.used_ip_numbers, start_octet + 1) && !contains(local.used_ip_numbers, start_octet + 2)
    }
  ]
  
  # Get the first available block
  first_available_block = [
    for candidate in local.scan_candidates :
    candidate if candidate.is_available
  ][0]
  
  # Build the Kafka IP range
  kafka_range_discovered = local.first_available_block != null ? [
    "${local.network_base}.${local.first_available_block.start_ip}",
    "${local.network_base}.${local.first_available_block.end_ip}"
  ] : null
  
  # Use discovered range or manual override
  kafka_range_available = local.kafka_range_discovered != null ? local.kafka_range_discovered : (
    var.kafka_vip_pool_range_start != null && var.kafka_vip_pool_range_end != null ? [
      var.kafka_vip_pool_range_start,
      var.kafka_vip_pool_range_end
    ] : null
  )
  
  # Extract the first IP from the Kafka VIP pool range for the broker
  kafka_broker_ip = local.kafka_range_available != null ? local.kafka_range_available[0] : null
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

# Validation for Kafka pool range discovery
resource "null_resource" "validate_kafka_range" {
  lifecycle {
    precondition {
      condition = local.kafka_range_available != null && length(local.kafka_range_available) == 2
      error_message = <<-EOT
        Unable to find available IP range for Kafka VIP pool.
        
        Network base: ${local.network_base} (from main VIP pool)
        Total IP numbers in use: ${length(local.used_ip_numbers)}
        Used IP numbers: ${jsonencode(sort(tolist(local.used_ip_numbers)))}
        Available blocks found: ${local.kafka_range_discovered != null ? 1 : 0}
        
        All 3-IP consecutive blocks in range .50-.239 appear to be in use.
        
        Solution: Set manual override in terraform.tfvars:
        kafka_vip_pool_range_start = "10.143.11.220"
        kafka_vip_pool_range_end   = "10.143.11.222"
      EOT
    }
    
    precondition {
      condition = local.kafka_broker_ip != null
      error_message = "Kafka broker IP could not be determined from VIP pool range."
    }
  }
}

# Reference to main VIP pool (for database and S3)
data "vastdata_vip_pool" "main" {
  name = "main"
}

# Create new VIP pool for Kafka with dynamically discovered settings
resource "vastdata_vip_pool" "kafka_pool" {
  name        = var.kafka_vip_pool_name
  role        = "PROTOCOLS"
  subnet_cidr = local.main_pool_subnet_cidr     # Use same subnet as main pool
  ip_ranges   = [local.kafka_range_available]   # Dynamically discovered available range
  
  depends_on = [
    null_resource.validate_vip_ips,
    null_resource.validate_kafka_range
  ]
}