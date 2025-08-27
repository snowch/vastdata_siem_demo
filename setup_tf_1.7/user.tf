data "vastdata_non_local_user" "the_user" {
  username = var.user_name
  context = var.user_context
  tenant_id = data.vastdata_tenant.the_tenant.id
}

resource "vastdata_non_local_user_key" "demo_key" {
  uid       = data.vastdata_non_local_user.the_user.uid
  tenant_id = data.vastdata_tenant.the_tenant.id
  enabled   = true
}