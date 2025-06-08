# OCSF Implementation Guide for Traffic Simulator

## Overview

This guide explains how to configure Fluentd to output events in OCSF (Open Cybersecurity Schema Framework) standard format.

## What is OCSF?

OCSF is an open standard that provides a unified data schema for cybersecurity events, enabling:
- **Standardized event formats** across security tools
- **Better SIEM integration** and analytics
- **Improved interoperability** between security platforms
- **Enhanced threat detection** through consistent data structures

## Should You Implement OCSF?

**YES** - Here's why:

### Benefits for Your Traffic Simulator:
1. **Industry Compliance** - OCSF is becoming the standard for security data
2. **SIEM Ready** - Major SIEMs (Splunk, QRadar, Sentinel) support OCSF
3. **Better Analytics** - Standardized fields enable advanced correlation
4. **Future-Proof** - Positions your simulator for modern security stacks
5. **Realistic Testing** - Provides production-like data formats

### Current vs OCSF Format:

**Current Format:**
```
2025-06-08 19:22:15.123 event=ssh_login_failure user=user42 src_ip=192.168.100.15 dst_ip=192.168.100.22
```

**OCSF Format:**
```json
{
  "class_uid": 3002,
  "activity_id": 2,
  "severity_id": 2,
  "actor": {
    "user": {
      "name": "user42",
      "type": "User"
    }
  },
  "src_endpoint": {
    "ip": "192.168.100.15"
  },
  "dst_endpoint": {
    "ip": "192.168.100.22"
  },
  "time_dt": "2025-06-08T19:22:15.123Z",
  "category_name": "Identity & Access Management",
  "type_name": "SSH Authentication"
}
```

## Implementation Steps

### 1. Use the OCSF Configuration

Replace your current Fluentd configuration:

```bash
# Backup current config
cp fluentd/conf/fluentd.conf fluentd/conf/fluentd.conf.backup

# Use OCSF configuration
cp fluentd/conf/fluentd-ocsf.conf fluentd/conf/fluentd.conf
```

### 2. OCSF Event Mappings

The configuration maps your events to OCSF classes:

| Your Event Type | OCSF Class | Class UID | Description |
|----------------|------------|-----------|-------------|
| ssh_login_* | Authentication | 3002 | User authentication events |
| web_login_* | Authentication | 3002 | Web authentication events |
| brute_force_attack | Security Finding | 2004 | Attack detection |
| sql_injection_attempt | Security Finding | 2004 | Attack detection |
| malware_detection | Malware Finding | 2001 | Malware events |
| data_exfiltration | Network Activity | 4002 | Network-based events |
| file_access | File Activity | 1001 | File system events |

### 3. Severity Levels

Events are automatically assigned OCSF severity levels:

- **Informational (1)**: Successful logins
- **Low (2)**: Failed logins
- **Medium (3)**: Brute force, SQL injection
- **High (4)**: Malware, data exfiltration

### 4. Testing the Implementation

1. **Start with OCSF config:**
   ```bash
   docker-compose up fluentd
   ```

2. **Generate test events:**
   ```bash
   curl -X POST http://localhost:8080/trigger_event \
     -H "Content-Type: application/json" \
     -d '{"event_type": "ssh_login_failure"}'
   ```

3. **Verify OCSF output in Kafka:**
   ```bash
   # Check Kafka topic for OCSF formatted events
   docker exec -it kafka kafka-console-consumer.sh \
     --bootstrap-server localhost:9092 \
     --topic security-events \
     --from-beginning
   ```

### 5. Advanced OCSF Features

#### Add Custom Fields
You can extend the OCSF transformation to include additional fields:

```ruby
# Add to fluentd-ocsf.conf
observables [
  {
    "name": "source_ip",
    "type": "IP Address",
    "value": "${record['src_ip']}"
  }
]
```

#### Enrich with Threat Intelligence
```ruby
# Add threat intel enrichment
enrichments {
  "threat_intel": {
    "source": "Custom TI",
    "confidence": 85
  }
}
```

## OCSF Schema Reference

### Key OCSF Fields Used:

- **class_uid**: Event classification (Authentication, Finding, etc.)
- **activity_id**: Action taken (Allow/Deny/Other)
- **severity_id**: Event severity (1-4 scale)
- **actor**: Who performed the action
- **src_endpoint/dst_endpoint**: Network endpoints
- **time_dt**: ISO 8601 timestamp
- **message**: Human-readable description

### OCSF Categories:

1. **Identity & Access Management** - Login events
2. **System Activity** - File operations
3. **Findings** - Security detections
4. **Network Activity** - Network-based events

## Benefits Realized

After implementing OCSF, you'll have:

✅ **Standardized Security Data** - Industry-standard event format
✅ **SIEM Integration Ready** - Compatible with major security platforms
✅ **Enhanced Analytics** - Rich metadata for correlation
✅ **Compliance Ready** - Meets modern security data requirements
✅ **Scalable Architecture** - Future-proof data pipeline

## Next Steps

1. **Test the OCSF configuration** with your existing events
2. **Validate output format** matches OCSF schema
3. **Integrate with your SIEM** using OCSF format
4. **Extend mappings** for additional event types as needed
5. **Consider OCSF validation** tools for schema compliance

## Resources

- [OCSF Official Documentation](https://schema.ocsf.io/)
- [OCSF GitHub Repository](https://github.com/ocsf/ocsf-schema)
- [Fluentd Record Transformer](https://docs.fluentd.org/filter/record_transformer)

---

**Recommendation**: Implement OCSF transformation to modernize your security data pipeline and improve integration capabilities with enterprise security tools.
