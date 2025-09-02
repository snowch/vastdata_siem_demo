#!/usr/bin/env python3
"""
Quick UID finder for your VastData system
Fixed version that handles port correctly
"""

import sys
import hashlib
from vastpy import VASTClient

def main():
    # Your VastData configuration
    host = "10.143.11.204:443"  # Include port in address
    user = "admin"
    password = "123456"
    tenant_name = "default"
    username = "cyberdemo"
    min_uid = 5000
    max_uid = 9999
    
    try:
        print(f"Connecting to VastData at {host}...")
        client = VASTClient(user=user, password=password, address=host)
        
        # Get tenant ID
        tenants = client.tenants.get(name=tenant_name)
        if not tenants:
            print(f"Error: Tenant '{tenant_name}' not found")
            return 1
        
        tenant_id = tenants[0]['id']
        print(f"Found tenant '{tenant_name}' with ID: {tenant_id}")
        
        # Get existing UIDs
        existing_uids = set()
        
        # Get users - try different approaches
        user_count = 0
        
        # Try to get users by tenant
        try:
            users_by_tenant = client.users.get(tenant_id=tenant_id)
            for user_obj in users_by_tenant:
                if 'uid' in user_obj and user_obj['uid'] is not None:
                    existing_uids.add(int(user_obj['uid']))
            user_count += len(users_by_tenant)
            print(f"Found {len(users_by_tenant)} users in tenant {tenant_id}")
        except Exception as e:
            print(f"Warning: Could not query users by tenant: {e}")
        
        # Try to get all users
        try:
            all_users = client.users.get()
            for user_obj in all_users:
                if 'uid' in user_obj and user_obj['uid'] is not None:
                    existing_uids.add(int(user_obj['uid']))
            print(f"Found {len(all_users)} total users (all tenants)")
            user_count = max(user_count, len(all_users))
        except Exception as e:
            print(f"Warning: Could not query all users: {e}")
        
        print(f"Total unique UIDs found: {len(existing_uids)}")
        if existing_uids:
            print(f"Existing UIDs: {sorted(list(existing_uids))[:10]}{'...' if len(existing_uids) > 10 else ''}")
        
        # Generate hash-based UID for consistency
        hash_input = f"{username}:{tenant_name}"
        hash_obj = hashlib.sha256(hash_input.encode())
        hash_int = int(hash_obj.hexdigest()[:8], 16)
        uid_range = max_uid - min_uid + 1
        hash_uid = min_uid + (hash_int % uid_range)
        
        print(f"\nHash-based UID for '{username}': {hash_uid}")
        
        # Check if hash UID is available
        if hash_uid not in existing_uids:
            print(f"✅ Hash-based UID {hash_uid} is available!")
            print(f"\n🎯 Add this to terraform.tfvars:")
            print(f"local_user_uid = {hash_uid}")
            return 0
        else:
            print(f"❌ Hash-based UID {hash_uid} is already taken")
        
        # Find first available UID
        print(f"\nSearching for available UID in range {min_uid}-{max_uid}...")
        for uid in range(min_uid, max_uid + 1):
            if uid not in existing_uids:
                print(f"✅ Found available UID: {uid}")
                print(f"\n🎯 Add this to terraform.tfvars:")
                print(f"local_user_uid = {uid}")
                return 0
        
        print(f"❌ No available UID found in range {min_uid}-{max_uid}")
        print(f"   Consider expanding the range or cleaning up unused users")
        return 1
        
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        return 1

if __name__ == '__main__':
    sys.exit(main())