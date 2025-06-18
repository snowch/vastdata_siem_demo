# dbt Observability - Monitoring dbt Run and Test Results

This implementation provides a comprehensive solution for monitoring dbt runs and storing the results in a database table for analysis and observability.

## Overview

The solution captures metadata about every dbt run including:
- Execution status (success/failure)
- Execution time
- Rows affected
- Resource type (model, test, seed, etc.)
- Database, schema, and table information
- Unique identifiers for tracking

## Components

### 1. dbt_results Model (`models/dbt_results.sql`)
- Creates a table to store dbt run results
- Configured as a regular table due to Trino connector limitations
- Note: Since it's not incremental, you may want to periodically clean old data

### 2. Result Parsing Macro (`macros/get_dbt_run_results.sql`)
- Extracts relevant fields from dbt's results object
- Flattens nested data structures
- Creates standardized result records

### 3. Upload Macro (`macros/upload_dbt_results.sql`)
- Called during on-run-end hook
- Inserts parsed results into the dbt_results table
- Includes logging for monitoring the upload process

### 4. Project Configuration (`dbt_project.yml`)
- Configures on-run-end hook to automatically capture results
- Runs after every dbt command execution
- No tests included to avoid validation conflicts with different dbt versions

## Setup Instructions

### 1. Create the Results Table
First, create the empty dbt_results table:
```bash
dbt run -m dbt_results
```

### 2. Test the Setup
Run any dbt command to test the observability:
```bash
dbt run
# or
dbt test
# or
dbt run -m summary_statistics
```

After execution, check the dbt_results table for captured data.

## Data Schema

The `dbt_results` table contains the following columns:

| Column | Type | Description |
|--------|------|-------------|
| result_id | varchar(500) | Unique identifier (invocation_id + unique_id) |
| invocation_id | varchar(100) | Unique ID for each dbt command execution |
| unique_id | varchar(500) | dbt's unique identifier for each resource |
| database_name | varchar(100) | Target database name |
| schema_name | varchar(100) | Target schema name |
| table_name | varchar(100) | Resource name (model, test, etc.) |
| resource_type | varchar(50) | Type of resource (model, test, seed, etc.) |
| status | varchar(20) | Execution status (success, error, skipped) |
| execution_time | double | Time taken to execute in seconds |
| rows_affected | bigint | Number of rows affected by the operation |
| bytes_processed | bigint | Bytes processed during execution |
| created_at | timestamp | Timestamp when the result was recorded |

## Use Cases

### 1. Performance Monitoring
```sql
-- Find slowest running models
SELECT 
    table_name,
    AVG(execution_time) as avg_execution_time,
    MAX(execution_time) as max_execution_time,
    COUNT(*) as run_count
FROM dbt_results 
WHERE resource_type = 'model' 
    AND status = 'success'
    AND created_at >= date_add('day', -30, CURRENT_DATE)
GROUP BY table_name
ORDER BY avg_execution_time DESC;
```

### 2. Failure Analysis
```sql
-- Identify failing tests and models
SELECT 
    resource_type,
    table_name,
    status,
    COUNT(*) as failure_count,
    MAX(created_at) as last_failure
FROM dbt_results 
WHERE status IN ('error', 'fail')
    AND created_at >= date_add('day', -7, CURRENT_DATE)
GROUP BY resource_type, table_name, status
ORDER BY failure_count DESC;
```

### 3. Test Coverage Analysis
```sql
-- Analyze test execution patterns
SELECT 
    DATE(created_at) as run_date,
    COUNT(CASE WHEN resource_type = 'test' THEN 1 END) as tests_run,
    COUNT(CASE WHEN resource_type = 'test' AND status = 'success' THEN 1 END) as tests_passed,
    COUNT(CASE WHEN resource_type = 'model' THEN 1 END) as models_run
FROM dbt_results 
WHERE created_at >= date_add('day', -30, CURRENT_DATE)
GROUP BY DATE(created_at)
ORDER BY run_date DESC;
```

### 4. Data Volume Tracking
```sql
-- Track data volume processed over time
SELECT 
    table_name,
    DATE(created_at) as run_date,
    SUM(rows_affected) as total_rows,
    SUM(bytes_processed) as total_bytes
FROM dbt_results 
WHERE resource_type = 'model' 
    AND status = 'success'
    AND created_at >= CURRENT_DATE - INTERVAL '30 days'
GROUP BY table_name, DATE(created_at)
ORDER BY run_date DESC, total_rows DESC;
```

## Benefits

1. **Performance Monitoring**: Track execution times and identify bottlenecks
2. **Failure Detection**: Quickly identify and analyze failed runs
3. **Test Coverage**: Monitor test execution and success rates
4. **Data Lineage**: Track which models and tests run together
5. **Operational Insights**: Understand dbt usage patterns and optimization opportunities

## Troubleshooting

### Common Issues

1. **Table doesn't exist error**: Make sure to run `dbt run -m dbt_results` first
2. **Permission errors**: Ensure dbt has INSERT permissions on the target schema
3. **Schema mismatch**: If you modify the schema, you may need to `--full-refresh` the model

### Debugging

Enable verbose logging to see the upload process:
```bash
dbt run --log-level debug
```

Check the logs for messages like:
- "Uploading X dbt results to dbt_results table"
- "Successfully uploaded dbt results"

## Advanced Configuration

### Custom Fields
You can extend the `get_dbt_run_results` macro to capture additional fields from the dbt results object or node metadata.

### Filtering Results
Modify the `upload_dbt_results` macro to filter which results are stored (e.g., only failures, only specific resource types).

### Alternative Storage
The macros can be modified to store results in different tables or even external systems like logging services.
