vast_host     = "10.143.11.203"
vast_port     = 443
vast_user     = "admin"
vast_password = "123456"

tenant_name   = "default"      # only the default tenant is supported

vip_pool_name        = "csnow_vip"
vip_pool_start_ip    = "172.200.203.211"
vip_pool_end_ip      = "172.200.203.212"
vip_pool_subnet_cidr = "16"

user_name     = "chris.snow"

# OPTION 1: Use local user directly (bypasses AD completely)
user_context  = "local"  # "local", "ad", "nis", or "ldap"

# OPTION 2: Try AD first (uncomment to use AD instead of local)
# user_context  = "ad"

enable_user_fallback = true    # Enable fallback to local user
create_local_user_if_ad_missing = true
local_user_password = null     # null = auto-generate password

database_view_path = "/csnow-db"
database_view_name = "csnow-db"

s3_view_path = "/csnow-s3"
s3_view_name = "csnow-s3"

kafka_view_path = "/csnow-kafka"
kafka_view_name = "csnow-kafka"
