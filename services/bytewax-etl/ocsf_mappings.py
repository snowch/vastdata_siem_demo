from typing import Dict

OCSF_CLASS_MAPPING = {
    "1001": "file_activity",
    "1002": "kernel_extension",  
    "1003": "kernel_activity",
    "1004": "memory_activity",
    "1005": "module_activity",
    "1006": "scheduled_job_activity",
    "1007": "process_activity",
    "2001": "authentication",
    "2002": "authorization", 
    "2003": "account_change",
    "2004": "security_finding",
    "3001": "network_activity",
    "3002": "http_activity",
    "3003": "dns_activity", 
    "3004": "dhcp_activity",
    "3005": "rdp_activity",
    "3006": "smb_activity",
    "3007": "ssh_activity",
    "3008": "ftp_activity",
    "3009": "email_activity",
    "4001": "network_file_activity",
    "4002": "email_file_activity",
    "4003": "email_url_activity",
    "4004": "web_resources_activity",
    "5001": "inventory_info",
    "5002": "device_config_state",
    "5003": "user_access",
    "6001": "compliance_finding",
    "6002": "detection_finding",
    "6003": "incident_finding",
    "6004": "security_finding",
    "6005": "vulnerability_finding"
}

def determine_event_class(ocsf_data: Dict) -> str:
    """Determine the event class from OCSF data"""
    if "class_uid" in ocsf_data:
        class_uid = str(ocsf_data["class_uid"])
        class_name = OCSF_CLASS_MAPPING.get(class_uid)
        if class_name:
            return f"{class_uid}_{class_name}"
        else:
            return f"class_{class_uid}"
    elif "type_name" in ocsf_data:
        type_name = ocsf_data["type_name"].lower().replace(" ", "_").replace("-", "_")
        return f"type_{type_name}"
    else:
        return "unknown_event"
