# main.tf - v3.0 with HTTP-based UID discovery information

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
    ACCESS_KEY=${local.access_key}
    SECRET_KEY=${local.secret_key}
    DATABASE_ENDPOINT=https://${data.vastdata_vip_pool.main.ip_ranges[0][0]}
    DATABASE_NAME=${var.database_view_name}
  EOT
  filename = "${path.cwd}/connection_details.txt"
  
  depends_on = [
    vastdata_user.create_local_user,
    vastdata_user_key.local_demo_key,
    vastdata_nonlocal_user_key.demo_key
  ]
}