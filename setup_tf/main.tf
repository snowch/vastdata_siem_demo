# main.tf

resource "vastdata_vip_pool" "demo_pool" {
  name        = "demo-vip-pool"
  subnet_cidr = 24
  role        = "PROTOCOLS"

  ip_ranges {
    start_ip = "11.0.0.2"
    end_ip   = "11.0.0.3"
  }
}

resource "vastdata_user" "demo_user" {
  name                = var.database_owner
  uid                 = 555
  allow_create_bucket = true
  s3_superuser        = true
}

resource "vastdata_user_key" "demo_key" {
  user_id = vastdata_user.demo_user.id
}

resource "vastdata_view" "demo_view" {
  path         = var.database_view_path
  protocols    = ["S3", "DATABASE"]
  bucket       = var.database_name
  bucket_owner = vastdata_user.demo_user.name
  create_dir   = true
  policy_id    = 3

  depends_on = [vastdata_vip_pool.demo_pool]
}

resource "local_file" "connection_details" {
  content = <<-EOT
    DATABASE_OWNER=${var.database_owner}
    DATABASE_VIEW_PATH=${var.database_view_path}
    DATABASE_NAME=${var.database_name}
    ACCESS_KEY=${vastdata_user_key.demo_key.access_key}
    SECRET_KEY=${vastdata_user_key.demo_key.secret_key}
  EOT
  filename = "${path.cwd}/connection_details.txt"
}
