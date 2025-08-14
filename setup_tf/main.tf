# main.tf

data "vastdata_tenant" "the_tenant" {
  name = var.tenant_name
}

resource "local_file" "connection_details" {
  content = <<-EOT
    DATABASE_OWNER=${var.database_owner}
    DATABASE_VIEW_PATH=${var.database_view_path}
    DATABASE_NAME=${var.database_name}
    ACCESS_KEY=${vastdata_non_local_user_key.demo_key.access_key}
    SECRET_KEY=${vastdata_non_local_user_key.demo_key.secret_key}
  EOT
  filename = "${path.cwd}/connection_details.txt"
}
