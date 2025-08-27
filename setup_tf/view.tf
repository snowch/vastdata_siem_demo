# view.tf - v2.0 with dynamic user support

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
}

resource "vastdata_view" "s3_view" {
  path         = var.s3_view_path
  protocols    = ["S3", "DATABASE"]
  bucket       = var.s3_view_name
  bucket_owner = local.username
  create_dir   = true
  policy_id    = data.vastdata_view_policy.s3policy.id
}

resource "vastdata_view" "kafka_view" {
  path            = var.kafka_view_path
  protocols       = ["S3", "DATABASE", "KAFKA"]
  bucket          = var.kafka_view_name
  bucket_owner    = local.username
  create_dir      = true
  policy_id       = data.vastdata_view_policy.s3policy.id
  kafka_vip_pools = [vastdata_vip_pool.pool1.id]
}