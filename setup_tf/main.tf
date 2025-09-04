# main.tf - v6.0 with Docker-based Kafka topic creation

data "vastdata_tenant" "the_tenant" {
  name = var.tenant_name
}

resource "local_file" "connection_details" {
  content = <<-EOT
    OPENAI_API_KEY=_SET_THIS_

    # Vast Data DB Credentials
    VASTDB_ACCESS_KEY=${local.access_key}
    VASTDB_SECRET_KEY=${local.secret_key}
    VASTDB_ENDPOINT=https://${local.database_ip_1}
    VASTDB_DATA_ENDPOINTS=https://${local.database_ip_1}
    
    VASTDB_ZEEK_BUCKET=${var.database_view_name}
    VASTDB_FLUENTD_BUCKET=${var.database_view_name}

    VASTDB_ZEEK_SCHEMA=siem
    VASTDB_ZEEK_TABLE_PREFIX="zeek_"

    VASTDB_FLUENTD_SCHEMA=siem
    VASTDB_FLUENTD_TABLE_PREFIX="fluentd_"

    # KAFKA Configuration
    KAFKA_BROKER=${local.kafka_broker_ip}:9092
    KAFKA_ZEEK_TOPIC=${var.kafka_zeek_topic}
    KAFKA_EVENT_LOG_TOPIC=${var.kafka_event_log_topic}

    # Network Interface in docker container to Monitor with Zeek
    MONITOR_INTERFACE=eth0

    # Jupyter Configuration
    JUPYTER_PASSWORD=123456

    # ChromaDB Configuration
    CHROMA_HOST=chroma
    CHROMA_PORT=8000
    CHROMA_COLLECTION=security_events_dual

    # AI Model Configuration
    AI_MODEL=gpt-4o-mini
    MAX_TOKENS=90000
    MODEL_TEMPERATURE=0.7
    MODEL_TIMEOUT=1200

    # Workflow Configuration
    MAX_AGENTS=6
    APPROVAL_TIMEOUT=300
    MAX_MESSAGES=60
    ENABLE_STRUCTURED_OUTPUT=true

    # Server Configuration
    SERVER_HOST=0.0.0.0
    PORT=5000
    DEBUG=false
    CORS_ORIGINS=*
    LOG_LEVEL=INFO

    # Terraform metadata:
    #
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
    # TOPIC_CREATION_METHOD: Manual script provided

  EOT
  filename = "${path.cwd}/connection_details.txt"
  
  depends_on = [
    vastdata_user.create_local_user,
    vastdata_user_key.local_demo_key,
    vastdata_nonlocal_user_key.demo_key,
    null_resource.validate_vip_ips,
    null_resource.validate_kafka_range,
    vastdata_vip_pool.kafka_pool,
  ]
}