{% macro upload_dbt_results(results) %}

  {% if execute %}
    {% set results_list = get_dbt_run_results(results) %}
    
    {% if results_list | length > 0 %}
      {% set insert_sql %}
        insert into "{{ target.database }}"."{{ target.schema }}".dbt_results (
          result_id,
          invocation_id,
          unique_id,
          database_name,
          schema_name,
          table_name,
          resource_type,
          status,
          execution_time,
          rows_affected,
          bytes_processed,
          created_at
        ) values
        {% for result in results_list %}
          (
            cast('{{ result.result_id }}' as varchar(500)),
            cast('{{ result.invocation_id }}' as varchar(100)),
            cast('{{ result.unique_id }}' as varchar(500)),
            cast('{{ result.database_name }}' as varchar(100)),
            cast('{{ result.schema_name }}' as varchar(100)),
            cast('{{ result.table_name }}' as varchar(100)),
            cast('{{ result.resource_type }}' as varchar(50)),
            cast('{{ result.status }}' as varchar(20)),
            cast({{ result.execution_time }} as double),
            cast({{ result.rows_affected }} as bigint),
            cast({{ result.bytes_processed }} as bigint),
            cast('{{ result.created_at }}' as timestamp)
          ){% if not loop.last %},{% endif %}
        {% endfor %}
      {% endset %}
      
      {% do log("Uploading " ~ results_list | length ~ " dbt results to dbt_results table", info=true) %}
      {% do run_query(insert_sql) %}
      {% do log("Successfully uploaded dbt results", info=true) %}
    {% endif %}
  {% endif %}

{% endmacro %}
