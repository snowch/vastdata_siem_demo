import os
import trino
import json
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def get_logs():    
    trino_host = 'trino'
    trino_port = 8080
    trino_user = 'admin'
    trino_catalog = 'vast'
    trino_db = os.getenv('VASTDB_FLUENTD_BUCKET', 'csnow-db')
    trino_schema = os.getenv('VASTDB_FLUENTD_SCHEMA', 'siem')

    logs = []
    try:
        with trino.dbapi.connect(
            host=trino_host,
            port=trino_port,
            user=trino_user,
            catalog=trino_catalog,
            schema=trino_schema
        ) as connection:
            cursor = connection.cursor()
            query = f"""
                SELECT raw_data, time_dt
                FROM "{trino_db}|{trino_schema}"."fluentd_detection_finding"
                ORDER BY time_dt DESC
                LIMIT 20
            """
            cursor.execute(query)
            rows = cursor.fetchall()
            # logger.debug(f"Rows {len(rows)}")
            for row in rows:
                try:
                    json_row = json.loads(row[0])
                    json_row['time_dt'] = row[1]
                    # Assuming raw_data is a JSON string
                    logs.append(json_row)
                except json.JSONDecodeError:
                    # If raw_data is not a JSON string, append as is or handle differently
                    logs.append({"raw_data": row[0], "parse_error": "Not a valid JSON string"})
        return logs
    except Exception as e:
        logger.error(e)
        raise(e)
