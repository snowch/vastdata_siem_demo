import os
import trino
import json
import logging
from core.config import settings

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def get_logs():
    logs = []
    try:
        with trino.dbapi.connect(
            host=settings.trino_host,
            port=settings.trino_port,
            user=settings.trino_user,
            catalog=settings.trino_catalog,
            schema=settings.trino_schema
        ) as connection:
            cursor = connection.cursor()
            query = f"""
                SELECT raw_data, time_dt
                FROM "{settings.trino_db}|{settings.trino_schema}"."fluentd_detection_finding"
                ORDER BY time_dt DESC
                LIMIT 20
            """
            cursor.execute(query)
            rows = cursor.fetchall()

            logger.debug(f"Rows {{len(rows)}} | Query {{query}}")
            for row in rows:
                try:
                    json_row = json.loads(row[0])
                    json_row['time_dt'] = row[1].isoformat() if hasattr(row[1], 'isoformat') else row[1]
                    # Assuming raw_data is a JSON string
                    logs.append(json_row)
                except json.JSONDecodeError:
                    # If raw_data is not a JSON string, append as is or handle differently
                    logs.append({"raw_data": row[0], "parse_error": "Not a valid JSON string"})
        return logs
    except Exception as e:
        logger.error(e)
        raise(e)
