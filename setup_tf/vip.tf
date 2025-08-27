# vip.tf - v2.0 syntax

data "vastdata_vip_pool" "main" {
  name = "main"
}

resource "vastdata_vip_pool" "pool1" {
  name        = var.vip_pool_name
  role        = "PROTOCOLS"
  subnet_cidr = var.vip_pool_subnet_cidr
  
  # v2.0 uses block syntax instead of array
  ip_ranges {
    start_ip = var.vip_pool_start_ip
    end_ip   = var.vip_pool_end_ip
  }
}