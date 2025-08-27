# vip.tf - v2.0 syntax corrected

data "vastdata_vip_pool" "main" {
  name = "main"
}

resource "vastdata_vip_pool" "pool1" {
  name        = var.vip_pool_name
  role        = "PROTOCOLS"
  subnet_cidr = var.vip_pool_subnet_cidr
  
  # Try as a list of lists - each range is a list of [start, end]
  ip_ranges = [[var.vip_pool_start_ip, var.vip_pool_end_ip]]
}