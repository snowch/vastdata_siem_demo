{{ config(materialized='table') }}

SELECT
    'zeek_weird' AS table_name,
    COUNT(*) AS total_records,
    MAX(ts) AS last_updated
FROM
    {{ source('zeek', 'zeek_weird') }}

UNION ALL

SELECT
    'zeek_known_hosts' AS table_name,
    COUNT(*) AS total_records,
    MAX(ts) AS last_updated
FROM
    {{ source('zeek', 'zeek_known_hosts') }}

UNION ALL

SELECT
    'zeek_http' AS table_name,
    COUNT(*) AS total_records,
    MAX(ts) AS last_updated
FROM
    {{ source('zeek', 'zeek_http') }}

UNION ALL

SELECT
    'zeek_conn' AS table_name,
    COUNT(*) AS total_records,
    MAX(ts) AS last_updated
FROM
    {{ source('zeek', 'zeek_conn') }}

UNION ALL

SELECT
    'zeek_analyzer' AS table_name,
    COUNT(*) AS total_records,
    MAX(ts) AS last_updated
FROM
    {{ source('zeek', 'zeek_analyzer') }}

UNION ALL

SELECT
    'zeek_ftp' AS table_name,
    COUNT(*) AS total_records,
    MAX(ts) AS last_updated
FROM
    {{ source('zeek', 'zeek_ftp') }}

UNION ALL

SELECT
    'zeek_dns' AS table_name,
    COUNT(*) AS total_records,
    MAX(ts) AS last_updated
FROM
    {{ source('zeek', 'zeek_dns') }}

UNION ALL

SELECT
    'fluentd_file_system_activity' AS table_name,
    COUNT(*) AS total_records,
    MAX(time_dt) AS last_updated
FROM
    {{ source('fluentd', 'fluentd_file_system_activity') }}

UNION ALL

SELECT
    'fluentd_authentication' AS table_name,
    COUNT(*) AS total_records,
    MAX(time_dt) AS last_updated
FROM
    {{ source('fluentd', 'fluentd_authentication') }}

UNION ALL

SELECT
    'fluentd_detection_finding' AS table_name,
    COUNT(*) AS total_records,
    MAX(time_dt) AS last_updated
FROM
    {{ source('fluentd', 'fluentd_detection_finding') }}
