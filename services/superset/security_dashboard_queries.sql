-- =====================================================
-- SECURITY DASHBOARD SQL QUERIES
-- For visualizing malicious activity from OCSF and Zeek data
-- =====================================================

-- 1. MALICIOUS ACTIVITY OVERVIEW - Event Types Over Time
-- Chart Type: Time Series Line Chart
-- Purpose: Show trends of different attack types over time
SELECT 
    DATE_TRUNC('hour', time_dt) as time_bucket,
    original_event_type,
    COUNT(*) as event_count
FROM ocsf_events 
WHERE original_event_type IN (
    'ssh_login_failure', 'rdp_login_failure', 'brute_force_attack', 
    'rdp_brute_force', 'sql_injection_attempt', 'malware_detection',
    'data_exfiltration', 'rdp_reconnaissance'
)
AND time_dt >= NOW() - INTERVAL '24 hours'
GROUP BY time_bucket, original_event_type
ORDER BY time_bucket, original_event_type;

-- 2. TOP ATTACKERS BY SOURCE IP
-- Chart Type: Horizontal Bar Chart
-- Purpose: Identify most active malicious source IPs
SELECT 
    src_ip,
    COUNT(*) as total_attacks,
    COUNT(DISTINCT original_event_type) as attack_types,
    STRING_AGG(DISTINCT original_event_type, ', ') as attack_methods
FROM ocsf_events 
WHERE original_event_type IN (
    'ssh_login_failure', 'rdp_login_failure', 'brute_force_attack',
    'rdp_brute_force', 'sql_injection_attempt', 'malware_detection',
    'data_exfiltration', 'rdp_reconnaissance'
)
AND time_dt >= NOW() - INTERVAL '7 days'
GROUP BY src_ip
HAVING COUNT(*) > 5
ORDER BY total_attacks DESC
LIMIT 20;

-- 3. ATTACK SUCCESS VS FAILURE RATES
-- Chart Type: Donut/Pie Chart
-- Purpose: Show ratio of successful vs failed attacks
SELECT 
    CASE 
        WHEN original_event_type LIKE '%_success' THEN 'Successful Attacks'
        WHEN original_event_type LIKE '%_failure' OR 
             original_event_type IN ('brute_force_attack', 'rdp_brute_force', 'sql_injection_attempt') 
        THEN 'Failed Attacks'
        ELSE 'Other Malicious Activity'
    END as attack_outcome,
    COUNT(*) as count,
    ROUND(COUNT(*) * 100.0 / SUM(COUNT(*)) OVER (), 2) as percentage
FROM ocsf_events 
WHERE time_dt >= NOW() - INTERVAL '24 hours'
GROUP BY attack_outcome
ORDER BY count DESC;

-- 4. BRUTE FORCE ATTACK PATTERNS
-- Chart Type: Heatmap
-- Purpose: Show brute force attempts by hour and day
SELECT 
    EXTRACT(DOW FROM time_dt) as day_of_week,
    EXTRACT(HOUR FROM time_dt) as hour_of_day,
    COUNT(*) as attack_count
FROM ocsf_events 
WHERE original_event_type IN ('brute_force_attack', 'rdp_brute_force', 'ssh_login_failure', 'rdp_login_failure')
AND time_dt >= NOW() - INTERVAL '7 days'
GROUP BY day_of_week, hour_of_day
ORDER BY day_of_week, hour_of_day;

-- 5. TARGETED SERVICES AND PORTS
-- Chart Type: Stacked Bar Chart
-- Purpose: Show which services/ports are being targeted
SELECT 
    CASE 
        WHEN dst_port = 22 THEN 'SSH (22)'
        WHEN dst_port = 3389 THEN 'RDP (3389)'
        WHEN dst_port = 80 THEN 'HTTP (80)'
        WHEN dst_port = 443 THEN 'HTTPS (443)'
        WHEN dst_port = 445 THEN 'SMB (445)'
        ELSE CONCAT('Port ', dst_port)
    END as service,
    original_event_type,
    COUNT(*) as attack_count
FROM ocsf_events 
WHERE dst_port IS NOT NULL
AND original_event_type IN (
    'ssh_login_failure', 'rdp_login_failure', 'brute_force_attack',
    'rdp_brute_force', 'sql_injection_attempt', 'file_access'
)
AND time_dt >= NOW() - INTERVAL '24 hours'
GROUP BY service, original_event_type
ORDER BY attack_count DESC;

-- 6. SQL INJECTION ATTACK TRENDS (from Zeek Notice data)
-- Chart Type: Time Series Area Chart
-- Purpose: Track SQL injection attempts over time
SELECT 
    DATE_TRUNC('hour', ts) as time_bucket,
    src as attacker_ip,
    COUNT(*) as injection_attempts
FROM zeek_notice 
WHERE note = 'HTTP::SQL_Injection_Attacker'
AND ts >= NOW() - INTERVAL '24 hours'
GROUP BY time_bucket, src
ORDER BY time_bucket, injection_attempts DESC;

-- 7. NETWORK PROTOCOL VIOLATIONS (from Zeek Weird data)
-- Chart Type: Treemap
-- Purpose: Visualize different types of protocol violations
SELECT 
    analyzer_name as protocol,
    cause as violation_type,
    COUNT(*) as violation_count,
    COUNT(DISTINCT "id.orig_h") as unique_sources
FROM zeek_weird 
WHERE ts >= NOW() - INTERVAL '24 hours'
GROUP BY protocol, violation_type
HAVING COUNT(*) > 5
ORDER BY violation_count DESC;

-- 8. SUSPICIOUS FTP ACTIVITY
-- Chart Type: Scatter Plot
-- Purpose: Identify unusual FTP file transfers
SELECT 
    DATE_TRUNC('hour', ts) as time_bucket,
    "id.orig_h" as source_ip,
    "id.resp_h" as ftp_server,
    command,
    COUNT(*) as transfer_count,
    STRING_AGG(DISTINCT arg, ', ') as files
FROM zeek_ftp 
WHERE ts >= NOW() - INTERVAL '24 hours'
AND command IN ('STOR', 'RETR')
GROUP BY time_bucket, source_ip, ftp_server, command
HAVING COUNT(*) > 10  -- Suspicious high volume
ORDER BY transfer_count DESC;

-- 9. GEOLOCATION ATTACK HEATMAP
-- Chart Type: Geographic Map
-- Purpose: Show attack origins by IP geolocation (requires IP geolocation data)
SELECT 
    src_ip,
    COUNT(*) as total_attacks,
    COUNT(DISTINCT dst_ip) as targets_hit,
    STRING_AGG(DISTINCT original_event_type, ', ') as attack_types,
    -- Add geolocation fields if available
    -- country, city, latitude, longitude
    MAX(time_dt) as last_seen
FROM ocsf_events 
WHERE original_event_type IN (
    'ssh_login_failure', 'rdp_login_failure', 'brute_force_attack',
    'rdp_brute_force', 'sql_injection_attempt', 'malware_detection'
)
AND time_dt >= NOW() - INTERVAL '7 days'
GROUP BY src_ip
HAVING COUNT(*) > 10
ORDER BY total_attacks DESC;

-- 10. USER ACCOUNT COMPROMISE INDICATORS
-- Chart Type: Table with Risk Scoring
-- Purpose: Identify potentially compromised user accounts
SELECT 
    user_name,
    COUNT(*) as total_events,
    COUNT(CASE WHEN original_event_type LIKE '%_failure' THEN 1 END) as failed_attempts,
    COUNT(CASE WHEN original_event_type LIKE '%_success' THEN 1 END) as successful_logins,
    COUNT(DISTINCT src_ip) as unique_source_ips,
    COUNT(DISTINCT dst_ip) as unique_targets,
    -- Risk scoring
    CASE 
        WHEN COUNT(CASE WHEN original_event_type LIKE '%_failure' THEN 1 END) > 20 THEN 'HIGH'
        WHEN COUNT(CASE WHEN original_event_type LIKE '%_failure' THEN 1 END) > 10 THEN 'MEDIUM'
        ELSE 'LOW'
    END as risk_level,
    MIN(time_dt) as first_seen,
    MAX(time_dt) as last_seen
FROM ocsf_events 
WHERE user_name IS NOT NULL
AND time_dt >= NOW() - INTERVAL '24 hours'
GROUP BY user_name
HAVING COUNT(*) > 5
ORDER BY failed_attempts DESC, unique_source_ips DESC;

-- 11. NETWORK CONNECTION ANOMALIES (from Zeek Conn data)
-- Chart Type: Bubble Chart
-- Purpose: Identify unusual connection patterns
SELECT 
    "id.orig_h" as source_ip,
    "id.resp_h" as dest_ip,
    "id.resp_p" as dest_port,
    service,
    COUNT(*) as connection_count,
    SUM(orig_bytes) as total_bytes_sent,
    SUM(resp_bytes) as total_bytes_received,
    AVG(duration) as avg_duration,
    -- Anomaly indicators
    CASE 
        WHEN COUNT(*) > 1000 THEN 'High Volume'
        WHEN SUM(orig_bytes) > 1000000 THEN 'Large Upload'
        WHEN SUM(resp_bytes) > 1000000 THEN 'Large Download'
        WHEN AVG(duration) > 3600 THEN 'Long Duration'
        ELSE 'Normal'
    END as anomaly_type
FROM zeek_conn 
WHERE ts >= NOW() - INTERVAL '24 hours'
AND proto = 'tcp'
GROUP BY source_ip, dest_ip, dest_port, service
HAVING COUNT(*) > 50 OR SUM(orig_bytes) > 100000 OR SUM(resp_bytes) > 100000
ORDER BY connection_count DESC;

-- 12. ATTACK TIMELINE CORRELATION
-- Chart Type: Gantt Chart / Timeline
-- Purpose: Show attack sequences and timing
WITH attack_sessions AS (
    SELECT 
        src_ip,
        dst_ip,
        user_name,
        original_event_type,
        time_dt,
        LAG(time_dt) OVER (PARTITION BY src_ip, dst_ip ORDER BY time_dt) as prev_event_time,
        LEAD(time_dt) OVER (PARTITION BY src_ip, dst_ip ORDER BY time_dt) as next_event_time
    FROM ocsf_events 
    WHERE time_dt >= NOW() - INTERVAL '24 hours'
    AND original_event_type IN (
        'ssh_login_failure', 'rdp_login_failure', 'brute_force_attack',
        'rdp_brute_force', 'ssh_login_success', 'rdp_login_success'
    )
)
SELECT 
    src_ip,
    dst_ip,
    user_name,
    STRING_AGG(original_event_type ORDER BY time_dt, ', ') as attack_sequence,
    MIN(time_dt) as session_start,
    MAX(time_dt) as session_end,
    COUNT(*) as events_in_session,
    EXTRACT(EPOCH FROM (MAX(time_dt) - MIN(time_dt))) as session_duration_seconds
FROM attack_sessions
GROUP BY src_ip, dst_ip, user_name
HAVING COUNT(*) > 3
ORDER BY session_start;

-- 13. REAL-TIME THREAT FEED
-- Chart Type: Live Table/Stream
-- Purpose: Show current active threats
SELECT 
    time_dt,
    src_ip as "Source IP",
    dst_ip as "Target IP",
    user_name as "User",
    original_event_type as "Attack Type",
    CASE 
        WHEN original_event_type IN ('malware_detection', 'data_exfiltration') THEN 'CRITICAL'
        WHEN original_event_type IN ('rdp_brute_force', 'brute_force_attack') THEN 'HIGH'
        WHEN original_event_type IN ('sql_injection_attempt', 'rdp_reconnaissance') THEN 'MEDIUM'
        ELSE 'LOW'
    END as "Severity"
FROM ocsf_events 
WHERE time_dt >= NOW() - INTERVAL '1 hour'
AND original_event_type IN (
    'ssh_login_failure', 'rdp_login_failure', 'brute_force_attack',
    'rdp_brute_force', 'sql_injection_attempt', 'malware_detection',
    'data_exfiltration', 'rdp_reconnaissance'
)
ORDER BY time_dt DESC
LIMIT 100;

-- 14. WEEKLY SECURITY SUMMARY
-- Chart Type: Multi-metric Dashboard
-- Purpose: Executive summary of security posture
SELECT 
    'This Week' as period,
    COUNT(*) as total_security_events,
    COUNT(DISTINCT src_ip) as unique_attackers,
    COUNT(DISTINCT dst_ip) as unique_targets,
    COUNT(DISTINCT user_name) as affected_users,
    COUNT(CASE WHEN original_event_type LIKE '%_success' THEN 1 END) as successful_attacks,
    COUNT(CASE WHEN original_event_type IN ('malware_detection', 'data_exfiltration') THEN 1 END) as critical_incidents,
    ROUND(
        COUNT(CASE WHEN original_event_type LIKE '%_success' THEN 1 END) * 100.0 / 
        NULLIF(COUNT(*), 0), 2
    ) as attack_success_rate
FROM ocsf_events 
WHERE time_dt >= NOW() - INTERVAL '7 days'
AND original_event_type NOT LIKE '%_success'
UNION ALL
SELECT 
    'Previous Week' as period,
    COUNT(*) as total_security_events,
    COUNT(DISTINCT src_ip) as unique_attackers,
    COUNT(DISTINCT dst_ip) as unique_targets,
    COUNT(DISTINCT user_name) as affected_users,
    COUNT(CASE WHEN original_event_type LIKE '%_success' THEN 1 END) as successful_attacks,
    COUNT(CASE WHEN original_event_type IN ('malware_detection', 'data_exfiltration') THEN 1 END) as critical_incidents,
    ROUND(
        COUNT(CASE WHEN original_event_type LIKE '%_success' THEN 1 END) * 100.0 / 
        NULLIF(COUNT(*), 0), 2
    ) as attack_success_rate
FROM ocsf_events 
WHERE time_dt >= NOW() - INTERVAL '14 days'
AND time_dt < NOW() - INTERVAL '7 days'
AND original_event_type NOT LIKE '%_success';

-- =====================================================
-- ADVANCED ANALYTICS QUERIES
-- =====================================================

-- 15. BEHAVIORAL ANOMALY DETECTION
-- Chart Type: Anomaly Detection Chart
-- Purpose: Detect unusual patterns in user behavior
WITH user_baselines AS (
    SELECT 
        user_name,
        AVG(daily_events) as avg_daily_events,
        STDDEV(daily_events) as stddev_daily_events
    FROM (
        SELECT 
            user_name,
            DATE(time_dt) as event_date,
            COUNT(*) as daily_events
        FROM ocsf_events 
        WHERE time_dt >= NOW() - INTERVAL '30 days'
        AND time_dt < NOW() - INTERVAL '1 day'
        GROUP BY user_name, event_date
    ) daily_stats
    GROUP BY user_name
    HAVING COUNT(*) >= 7  -- At least 7 days of history
),
today_activity AS (
    SELECT 
        user_name,
        COUNT(*) as today_events
    FROM ocsf_events 
    WHERE DATE(time_dt) = CURRENT_DATE
    GROUP BY user_name
)
SELECT 
    t.user_name,
    t.today_events,
    b.avg_daily_events,
    CASE 
        WHEN t.today_events > (b.avg_daily_events + 2 * b.stddev_daily_events) THEN 'HIGH_ANOMALY'
        WHEN t.today_events > (b.avg_daily_events + b.stddev_daily_events) THEN 'MEDIUM_ANOMALY'
        ELSE 'NORMAL'
    END as anomaly_level,
    ROUND((t.today_events - b.avg_daily_events) / NULLIF(b.stddev_daily_events, 0), 2) as z_score
FROM today_activity t
JOIN user_baselines b ON t.user_name = b.user_name
WHERE t.today_events > (b.avg_daily_events + b.stddev_daily_events)
ORDER BY z_score DESC;
