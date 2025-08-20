import os

trino_host = 'trino'
trino_port = 8080
trino_user = 'admin'
trino_catalog = 'vast'
trino_db = os.getenv('VASTDB_FLUENTD_BUCKET')
trino_schema = os.getenv('VASTDB_FLUENTD_SCHEMA')

chroma_host = "chroma"
chroma_port = 8000
collection_name = "security_events_dual"
