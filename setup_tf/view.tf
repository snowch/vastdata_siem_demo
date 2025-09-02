# view.tf - v5.0 Uses main VIP pool for all services (no new pool creation)

data "vastdata_view_policy" "s3policy" {
  name = "s3_default_policy"
}

resource "vastdata_view" "database_view" {
  path         = var.database_view_path
  protocols    = ["S3", "DATABASE"]
  bucket       = var.database_view_name
  bucket_owner = local.username
  create_dir   = true
  policy_id    = data.vastdata_view_policy.s3policy.id
  
  depends_on = [
    vastdata_user.create_local_user,
    vastdata_user_key.local_demo_key
  ]
}

resource "vastdata_view" "s3_view" {
  path         = var.s3_view_path
  protocols    = ["S3", "DATABASE"]
  bucket       = var.s3_view_name
  bucket_owner = local.username
  create_dir   = true
  policy_id    = data.vastdata_view_policy.s3policy.id
  
  depends_on = [
    vastdata_user.create_local_user,
    vastdata_user_key.local_demo_key
  ]
}

resource "vastdata_view" "kafka_view" {
  path            = var.kafka_view_path
  protocols       = ["S3", "DATABASE", "KAFKA"]
  bucket          = var.kafka_view_name
  bucket_owner    = local.username
  create_dir      = true
  policy_id       = data.vastdata_view_policy.s3policy.id
  kafka_vip_pools = [vastdata_vip_pool.kafka_pool.id]  # <- Use dedicated Kafka VIP pool
  
  depends_on = [
    vastdata_user.create_local_user,
    vastdata_user_key.local_demo_key,
    vastdata_vip_pool.kafka_pool
  ]
}