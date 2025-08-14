# main.tf

data "vastdata_tenant" "the_tenant" {
  name = var.tenant_name
}

resource "local_file" "connection_details" {
  content = <<-EOT
    # USER: ${var.user_name}
    ACCESS_KEY=${vastdata_non_local_user_key.demo_key.access_key}
    SECRET_KEY=${vastdata_non_local_user_key.demo_key.secret_key}
    DATABASE_ENDPOINT=https://${data.vastdata_vip_pool.main.ip_ranges[0].start_ip}
    DATABASE_NAME=${var.database_view_name}
  EOT
  filename = "${path.cwd}/connection_details.txt"
}
