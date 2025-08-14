data "vastdata_view_policy" "s3policy" {
  name = "s3_default_policy"
}

resource "vastdata_view" "database_view" {
  path         = var.database_view_path
  protocols    = ["S3", "DATABASE"]
  bucket       = var.database_view_name
  bucket_owner = data.vastdata_non_local_user.the_user.username
  create_dir   = true
  policy_id    = data.vastdata_view_policy.s3policy.id
  # depends_on = [vastdata_vip_pool.demo_pool]
}

resource "vastdata_view" "s3_view" {
  path         = var.s3_view_path
  protocols    = ["S3", "DATABASE"]
  bucket       = var.s3_view_name
  bucket_owner = data.vastdata_non_local_user.the_user.username
  create_dir   = true
  policy_id    = data.vastdata_view_policy.s3policy.id
  # depends_on = [vastdata_vip_pool.demo_pool]
}