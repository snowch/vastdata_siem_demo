# outputs.tf - v7.0 with Docker-based Kafka topic management

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

output "vip_discovery_info" {
  description = "Information about HTTP-based VIP pool discovery and creation."
  value = {
    # Main pool info (for database endpoints)
    main_pool_found       = length(local.vip_pools_json) > 0 ? true : false
    main_pool_name        = try(local.main_vip_pool.name, "not_found")
    main_pool_id          = try(local.main_vip_pool.id, "not_found")
    main_pool_subnet_cidr = local.main_pool_subnet_cidr
    main_pool_usage       = "Database and S3 endpoints"
    
    # Kafka pool info (newly created)
    kafka_pool_name       = var.kafka_vip_pool_name
    kafka_pool_id         = vastdata_vip_pool.kafka_pool.id
    kafka_pool_range      = local.kafka_range_available
    kafka_pool_subnet_cidr = local.main_pool_subnet_cidr
    kafka_pool_usage      = "Dedicated Kafka services"
    kafka_broker_ip       = local.kafka_broker_ip
    
    # Dynamic discovery details
    total_existing_pools  = length(local.vip_pools_json)
    database_ip_1         = local.database_ip_1
    database_ip_2         = local.database_ip_2
    consecutive_ips_valid = local.consecutive_ips_valid
    candidates_scanned    = length(local.scan_candidates)
    first_available_block = local.first_available_block
    selected_range_method = local.kafka_range_discovered != null ? "auto_discovered" : "manual_override"
  }
}

output "database_endpoints" {
  description = "The discovered database endpoints from main VIP pool."
  value = {
    primary_endpoint = "https://${local.database_ip_1}"
    backup_endpoint  = "https://${local.database_ip_2}"
    source_pool      = "main VIP pool (discovered)"
  }
}

output "kafka_vip_pool_info" {
  description = "Information about the created Kafka VIP pool."
  value = {
    name         = vastdata_vip_pool.kafka_pool.name
    id           = vastdata_vip_pool.kafka_pool.id
    role         = vastdata_vip_pool.kafka_pool.role
    subnet_cidr  = vastdata_vip_pool.kafka_pool.subnet_cidr
    ip_ranges    = vastdata_vip_pool.kafka_pool.ip_ranges
    usage        = "Dedicated for Kafka services only"
    broker_ip    = local.kafka_broker_ip
    broker_url   = "${local.kafka_broker_ip}:9092"
  }
}

output "kafka_topics_info" {
  description = "Information about Docker-created Kafka topics."
  value = {
    creation_method = "Docker kafka-tools"
    zeek_topic = {
      name               = var.kafka_zeek_topic
      partitions         = var.kafka_topic_partitions
      replication_factor = var.kafka_topic_replication_factor
      managed_by         = "Docker provisioner"
    }
    event_log_topic = {
      name               = var.kafka_event_log_topic
      partitions         = var.kafka_topic_partitions
      replication_factor = var.kafka_topic_replication_factor
      managed_by         = "Docker provisioner"
    }
    broker_connection = "${local.kafka_broker_ip}:9092"
    verification_command = "docker run --rm --network host jforge/kafka-tools kafka-topics.sh --bootstrap-server ${local.kafka_broker_ip}:9092 --list"
  }
}

output "api_debug_info" {
  description = "Debug information about the VastData API calls (for troubleshooting)."
  value = {
    # UID discovery API info
    uid_api_url         = var.user_context == "local" ? data.http.existing_users[0].url : null
    uid_response_status = var.user_context == "local" ? data.http.existing_users[0].status_code : null
    users_found         = var.user_context == "local" ? length(local.existing_users_json) : null
    
    # VIP pool discovery API info  
    vip_api_url         = data.http.vip_pools.url
    vip_response_status = data.http.vip_pools.status_code
    vip_pools_found     = length(local.vip_pools_json)
    main_vip_pool_id    = try(local.main_vip_pool.id, "not_found")
    
    # Kafka topic creation info
    topic_creation_method = "Docker kafka-tools"
    kafka_pool_created    = vastdata_vip_pool.kafka_pool.id
    kafka_pool_name       = vastdata_vip_pool.kafka_pool.name
    kafka_broker_ip       = local.kafka_broker_ip
    all_existing_ranges   = local.all_existing_ranges
    network_base          = local.network_base
    scan_range           = "${local.network_base}.50 - ${local.network_base}.239"
    used_ip_numbers      = sort(tolist(local.used_ip_numbers))
    total_used_ip_numbers = length(local.used_ip_numbers)
  }
}