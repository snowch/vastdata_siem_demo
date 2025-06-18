{{ config(
    materialized='table'
) }}

select
    cast(null as varchar(500)) as result_id,
    cast(null as varchar(100)) as invocation_id,
    cast(null as varchar(500)) as unique_id,
    cast(null as varchar(100)) as database_name,
    cast(null as varchar(100)) as schema_name,
    cast(null as varchar(100)) as table_name,
    cast(null as varchar(50)) as resource_type,
    cast(null as varchar(20)) as status,
    cast(null as double) as execution_time,
    cast(null as bigint) as rows_affected,
    cast(null as bigint) as bytes_processed,
    cast(null as timestamp) as created_at

-- This where clause ensures the model creates an empty table
where 1 = 0
