{% macro get_dbt_run_results(results) %}

  {% set results_list = [] %}
  
  {% for result in results %}
    {% set result_dict = {
        'result_id': invocation_id ~ '.' ~ result.node.unique_id,
        'invocation_id': invocation_id,
        'unique_id': result.node.unique_id,
        'database_name': result.node.database,
        'schema_name': result.node.schema,
        'table_name': result.node.name,
        'resource_type': result.node.resource_type,
        'status': result.status,
        'execution_time': result.execution_time,
        'rows_affected': result.adapter_response.get('rows_affected', 0) if result.adapter_response else 0,
        'bytes_processed': result.adapter_response.get('bytes_processed', 0) if result.adapter_response else 0,
        'created_at': run_started_at.strftime('%Y-%m-%d %H:%M:%S')
    } %}
    {% do results_list.append(result_dict) %}
  {% endfor %}

  {{ return(results_list) }}

{% endmacro %}
