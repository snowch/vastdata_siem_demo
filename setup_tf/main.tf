# main.tf - v2.0 with corrected VIP pool access syntax

data "vastdata_tenant" "the_tenant" {
  name = var.tenant_name
}

resource "local_file" "connection_details" {
  content = <<-EOT
    # USER: ${local.username}
    # USER_TYPE: ${var.user_context}
    ACCESS_KEY=${local.access_key}
    SECRET_KEY=${local.secret_key}
    DATABASE_ENDPOINT=https://${data.vastdata_vip_pool.main.ip_ranges[0][0]}
    DATABASE_NAME=${var.database_view_name}
  EOT
  filename = "${path.cwd}/connection_details.txt"
}