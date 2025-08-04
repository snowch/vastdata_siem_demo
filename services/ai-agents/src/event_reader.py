import json

def get_log_events() -> str:
    """Generates a batch of simulated SIEM logs matching the simulator's schema."""
    logs = [
        {
            "timestamp": "2024-08-01T00:00:00",
            "event_type": "user_login",
            "user_id": "admin",
            "source_ip": "192.0.2.1",
            "hostname": "web-server-01"
        },
        {
            "timestamp": "2024-08-01T00:00:05",
            "event_type": "ssh_login_failure",
            "user_id": "root",
            "source_ip": "198.51.100.10",
            "hostname": "db-server-01"
        },
        {
            "timestamp": "2024-08-01T00:00:10",
            "event_type": "ssh_login_failure",
            "user_id": "root",
            "source_ip": "198.51.100.10",
            "hostname": "db-server-01"
        },
        {
            "timestamp": "2024-08-01T00:00:15",
            "event_type": "ssh_login_failure",
            "user_id": "root",
            "source_ip": "198.51.100.10",
            "hostname": "db-server-01"
        },
        {
            "timestamp": "2024-08-01T00:00:20",
            "event_type": "ssh_login_success",
            "user_id": "admin",
            "source_ip": "198.51.100.10",
            "hostname": "db-server-01"
        },
        {
            "timestamp": "2024-08-01T00:00:25",
            "event_type": "file_access",
            "user_id": "john.doe",
            "file_path": "/var/log/auth.log",
            "access_type": "read"
        }
    ]
    return json.dumps(logs, indent=2)
