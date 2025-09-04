# main.tf - v5.0 with Kafka broker and topics information

data "vastdata_tenant" "the_tenant" {
  name = var.tenant_name
}

resource "local_file" "connection_details" {
  content = <<-EOT
    # USER: ${local.username}
    # USER_TYPE: ${var.user_context}
    # DISCOVERED_UID: ${var.user_context == "local" ? local.discovered_uid : "N/A"}
    # UID_METHOD: ${var.user_context == "local" ? local.uid_discovery_method : "N/A"}
    # TOTAL_EXISTING_UIDS: ${var.user_context == "local" ? length(local.existing_uids) : "N/A"}
    # VIP_POOL_DISCOVERY: HTTP API
    # MAIN_VIP_POOL: ${try(local.main_vip_pool.name, "not_found")} (for database/S3)
    # KAFKA_VIP_POOL: ${var.kafka_vip_pool_name} (dedicated for Kafka)
    # MAIN_VIP_SUBNET_CIDR: ${local.main_pool_subnet_cidr}
    # DATABASE_IPS: ${local.database_ip_1}, ${local.database_ip_2}
    # MAIN_VIP_RANGE: ${local.first_range_start} - ${local.first_range_end}
    # KAFKA_VIP_RANGE: ${local.kafka_range_available[0]} - ${local.kafka_range_available[1]}
    # KAFKA_BROKER_IP: ${local.kafka_broker_ip}
    # KAFKA_TOPICS: ${var.kafka_zeek_topic}, ${var.kafka_event_log_topic}
    ACCESS_KEY=${local.access_key}
    SECRET_KEY=${local.secret_key}
    DATABASE_ENDPOINT=https://${local.database_ip_1}
    DATABASE_ENDPOINT_BACKUP=https://${local.database_ip_2}
    DATABASE_NAME=${var.database_view_name}
    KAFKA_BROKER=${local.kafka_broker_ip}:9092
    KAFKA_ZEEK_TOPIC=${var.kafka_zeek_topic}
    KAFKA_EVENT_LOG_TOPIC=${var.kafka_event_log_topic}
  EOT
  filename = "${path.cwd}/connection_details.txt"
  
  depends_on = [
    vastdata_user.create_local_user,
    vastdata_user_key.local_demo_key,
    vastdata_nonlocal_user_key.demo_key,
    null_resource.validate_vip_ips,
    null_resource.validate_kafka_range,
    vastdata_vip_pool.kafka_pool,
    kafka_topic.zeek_topic,
    kafka_topic.event_log_topic
  ]
}