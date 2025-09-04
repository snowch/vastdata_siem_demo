# kafka.tf - v1.0 Kafka topics and broker configuration

# Wait for Kafka VIP pool to be ready before creating topics
resource "null_resource" "wait_for_kafka" {
  depends_on = [
    vastdata_vip_pool.kafka_pool,
    vastdata_view.kafka_view
  ]
  
  # Add a small delay to ensure Kafka service is ready
  provisioner "local-exec" {
    command = "echo 'Waiting for Kafka service to be ready...' && sleep 30"
  }
}

# Create Zeek SIEM logs topic
resource "kafka_topic" "zeek_topic" {
  name               = var.kafka_zeek_topic
  partitions         = var.kafka_topic_partitions
  replication_factor = var.kafka_topic_replication_factor
  
  config = {}
  
  depends_on = [
    null_resource.wait_for_kafka
  ]
  
  lifecycle {
    prevent_destroy = false
  }
}

# Create Fluentd event logs topic
resource "kafka_topic" "event_log_topic" {
  name               = var.kafka_event_log_topic
  partitions         = var.kafka_topic_partitions
  replication_factor = var.kafka_topic_replication_factor
  
  config = {
  }
  
  depends_on = [
    null_resource.wait_for_kafka
  ]
  
  lifecycle {
    prevent_destroy = false
  }
}