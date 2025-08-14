data "vastdata_vip_pool" "main" {
  name = "main"
}

resource "vastdata_vip_pool" "pool1" {
  name        = var.vip_pool_name
  role        = "PROTOCOLS"
  subnet_cidr = var.vip_pool_subnet_cidr
  ip_ranges {
    start_ip   = var.vip_pool_start_ip
    end_ip     = var.vip_pool_end_ip
  }
}
