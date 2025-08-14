# resource "vastdata_vip_pool" "demo_pool" {
#   name        = "demo-vip-pool"
#   subnet_cidr = 24
#   role        = "PROTOCOLS"
# 
#   ip_ranges {
#     start_ip = "11.0.0.2"
#     end_ip   = "11.0.0.3"
#   }
# }
# 
# 
# resource "vastdata_view" "demo_view" {
#   path         = var.database_view_path
#   protocols    = ["S3", "DATABASE"]
#   bucket       = var.database_name
#   bucket_owner = data.vastdata_non_local_user.the_user.username
#   create_dir   = true
#   policy_id    = 3
# 
#   depends_on = [vastdata_vip_pool.demo_pool]
# }
