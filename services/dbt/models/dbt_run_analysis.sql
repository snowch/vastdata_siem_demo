{{ config(
    materialized='table'
) }}

with run_stats as (
    select
        date(created_at) as run_date,
        invocation_id,
        resource_type,
        status,
        count(*) as resource_count,
        sum(execution_time) as total_execution_time,
        avg(execution_time) as avg_execution_time,
        max(execution_time) as max_execution_time,
        sum(rows_affected) as total_rows_affected
    from {{ ref('dbt_results') }}
    where created_at >= date_add('day', -30, current_date)
    group by 1, 2, 3, 4
),

daily_summary as (
    select
        run_date,
        count(distinct invocation_id) as total_runs,
        sum(case when status = 'success' then resource_count else 0 end) as successful_resources,
        sum(case when status in ('error', 'fail') then resource_count else 0 end) as failed_resources,
        sum(resource_count) as total_resources,
        avg(total_execution_time) as avg_run_duration,
        sum(total_rows_affected) as daily_rows_processed
    from run_stats
    group by 1
),

performance_trends as (
    select
        table_name,
        resource_type,
        count(*) as run_count,
        avg(cast(execution_time as double)) as avg_execution_time,
        stddev(cast(execution_time as double)) as execution_time_stddev,
        min(execution_time) as min_execution_time,
        max(execution_time) as max_execution_time,
        sum(case when status = 'success' then 1 else 0 end) as success_count,
        sum(case when status in ('error', 'fail') then 1 else 0 end) as failure_count
    from {{ ref('dbt_results') }}
    where created_at >= date_add('day', -30, current_date)
    group by 1, 2
)

select
    'daily_summary' as metric_type,
    cast(run_date as varchar) as dimension_1,
    null as dimension_2,
    total_runs as metric_value_1,
    successful_resources as metric_value_2,
    failed_resources as metric_value_3,
    avg_run_duration as metric_value_4
from daily_summary

union all

select
    'performance_trends' as metric_type,
    table_name as dimension_1,
    resource_type as dimension_2,
    avg_execution_time as metric_value_1,
    success_count as metric_value_2,
    failure_count as metric_value_3,
    run_count as metric_value_4
from performance_trends
where run_count > 1  -- Only include resources that have run multiple times
