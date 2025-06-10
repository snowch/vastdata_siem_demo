#!/usr/bin/env python

import os
import sys

# Load and validate all mandatory environment variables
def validate_environment_variables():
    """Validate that all required environment variables are set"""
    required_env_vars = {
        "VASTDB_ENDPOINT": "VastDB endpoint URL",
        "VASTDB_ACCESS_KEY": "VastDB access key", 
        "VASTDB_SECRET_KEY": "VastDB secret key",
        "VASTDB_FLUENTD_BUCKET": "VastDB FLUENTD bucket name",
        "VASTDB_FLUENTD_SCHEMA": "VastDB FLUENTD schema name", 
        "KAFKA_BROKER": "Kafka broker address",
        "KAFKA_EVENT_LOG_TOPIC": "Kafka event log topic name"
    }
    
    missing_vars = []
    env_values = {}
    
    for var_name, description in required_env_vars.items():
        value = os.getenv(var_name)
        if not value:
            missing_vars.append(f"  {var_name}: {description}")
        else:
            env_values[var_name] = value
    
    if missing_vars:
        error_msg = "Missing required environment variables:\n" + "\n".join(missing_vars)
        error_msg += "\n\nPlease set all required environment variables before running this script."
        raise EnvironmentError(error_msg)
    
    return env_values

# Validate and load environment variables
try:
    env_vars = validate_environment_variables()
    VASTDB_ENDPOINT = env_vars["VASTDB_ENDPOINT"]
    VASTDB_ACCESS_KEY = env_vars["VASTDB_ACCESS_KEY"] 
    VASTDB_SECRET_KEY = env_vars["VASTDB_SECRET_KEY"]
    VASTDB_FLUENTD_BUCKET = env_vars["VASTDB_FLUENTD_BUCKET"]
    VASTDB_FLUENTD_SCHEMA = env_vars["VASTDB_FLUENTD_SCHEMA"]
    VAST_KAFKA_BROKER = env_vars["KAFKA_BROKER"]
    topic = env_vars["KAFKA_EVENT_LOG_TOPIC"]
except EnvironmentError as e:
    print(f"ERROR: {e}")
    sys.exit(1)

VASTDB_FLUENTD_TABLE_PREFIX = 'ocsf_'

use_vastkafka = True
if use_vastkafka:
    kafka_brokers = VAST_KAFKA_BROKER
else:
    raise Exception("KAFKA_BROKER environment variable is not set. Please set it to the Kafka broker address.")

# Print configurations
print(f"""
---
VASTDB_ENDPOINT={VASTDB_ENDPOINT}
VASTDB_ACCESS_KEY=****{VASTDB_ACCESS_KEY[-4:]}
VASTDB_SECRET_KEY=****{VASTDB_SECRET_KEY[-4:]}
VASTDB_FLUENTD_BUCKET={VASTDB_FLUENTD_BUCKET}
VASTDB_FLUENTD_SCHEMA={VASTDB_FLUENTD_SCHEMA}
VASTDB_FLUENTD_TABLE_PREFIX={VASTDB_FLUENTD_TABLE_PREFIX}
---
VAST_KAFKA_BROKER={VAST_KAFKA_BROKER}
topic={topic}
""")

# Create Vast DB schema if it doesn't exist.
import vastdb

session = vastdb.connect(endpoint=VASTDB_ENDPOINT, access=VASTDB_ACCESS_KEY, secret=VASTDB_SECRET_KEY)
with session.transaction() as tx:
    bucket = tx.bucket(VASTDB_FLUENTD_BUCKET)
    bucket.schema(VASTDB_FLUENTD_SCHEMA, fail_if_missing=False) or bucket.create_schema(VASTDB_FLUENTD_SCHEMA)

import socket
import pyspark
from pyspark.conf import SparkConf
from pyspark.sql import SparkSession
from pyspark.sql.functions import from_json, col, count, get_json_object, to_timestamp, lit, when, isnan, isnull, from_unixtime
from pyspark.sql.types import StructType, StructField, StringType, LongType, DoubleType, BooleanType, TimestampType, IntegerType
import threading
import time
import json
import logging

# Spark Configuration
conf = SparkConf()
conf.setAll([
    # ("spark.driver.host", socket.gethostbyname(socket.gethostname())),
    ("spark.sql.execution.arrow.pyspark.enabled", "false"),
    # VASTDB
    ("spark.sql.catalog.ndb", 'spark.sql.catalog.ndb.VastCatalog'),
    ("spark.ndb.endpoint", VASTDB_ENDPOINT),
    ("spark.ndb.data_endpoints", VASTDB_ENDPOINT),
    ("spark.ndb.access_key_id", VASTDB_ACCESS_KEY),
    ("spark.ndb.secret_access_key", VASTDB_SECRET_KEY),
    ("spark.driver.extraClassPath", '/usr/local/spark/jars/spark3-vast-3.4.1-f93839bfa38a/*'),
    ("spark.executor.extraClassPath", '/usr/local/spark/jars/spark3-vast-3.4.1-f93839bfa38a/*'),
    ("spark.sql.extensions", 'ndb.NDBSparkSessionExtension'),
    # Kafka
    ("spark.jars.packages", "org.apache.spark:spark-sql-kafka-0-10_2.13:3.4.3," 
                            "org.apache.logging.log4j:log4j-slf4j2-impl:2.19.0," 
                            "org.apache.logging.log4j:log4j-api:2.19.0," 
                            "org.apache.logging.log4j:log4j-core:2.19.0"),
    ("spark.jars.excludes", "org.slf4j:slf4j-api,org.slf4j:slf4j-log4j12"),
    # ("spark.hadoop.fs.file.impl", "org.apache.hadoop.fs.RawLocalFileSystem"),
])

spark = SparkSession.builder \
    .appName("FluentDOCSFStreamingToVastDB") \
    .config(conf=conf) \
    .enableHiveSupport() \
    .getOrCreate()

sc = spark.sparkContext
sc.setLogLevel("WARN")

print("Spark successfully loaded\n")

destination_table_name_prefix = f"`ndb`.`{VASTDB_FLUENTD_BUCKET}`.`{VASTDB_FLUENTD_SCHEMA}`.`{VASTDB_FLUENTD_TABLE_PREFIX}`"
print(f"Table prefix: {destination_table_name_prefix}")

import os
import signal
import time
import threading
import pyspark
from pyspark.sql.functions import col, from_json
from pyspark.sql.types import *

# Create checkpoint directory with absolute path
checkpoint_dir = os.path.abspath("/tmp/spark_fluentd_checkpoint")
os.makedirs(checkpoint_dir, exist_ok=True)

# Global variables for tracking
total_message_count = 0
table_row_counts = {}  # Track row counts per table
last_batch_id = 0
last_batch_size = 0
processed_event_classes = set()  # Track which OCSF event classes we've seen
created_tables = set()  # Track which tables we've already created

should_shutdown = False

# OCSF Class UID to Name mapping (major classes)
OCSF_CLASS_MAPPING = {
    "1001": "file_activity",
    "1002": "kernel_extension",  
    "1003": "kernel_activity",
    "1004": "memory_activity",
    "1005": "module_activity",
    "1006": "scheduled_job_activity",
    "1007": "process_activity",
    "2001": "authentication",
    "2002": "authorization", 
    "2003": "account_change",
    "2004": "security_finding",
    "3001": "network_activity",
    "3002": "http_activity",
    "3003": "dns_activity", 
    "3004": "dhcp_activity",
    "3005": "rdp_activity",
    "3006": "smb_activity",
    "3007": "ssh_activity",
    "3008": "ftp_activity",
    "3009": "email_activity",
    "4001": "network_file_activity",
    "4002": "email_file_activity",
    "4003": "email_url_activity",
    "4004": "web_resources_activity",
    "5001": "inventory_info",
    "5002": "device_config_state",
    "5003": "user_access",
    "6001": "compliance_finding",
    "6002": "detection_finding",
    "6003": "incident_finding",
    "6004": "security_finding",
    "6005": "vulnerability_finding"
}

# Print a comprehensive status update
def print_status(source=""):
    global total_message_count, table_row_counts, last_batch_id, last_batch_size, processed_event_classes
    if not should_shutdown:
        current_time = time.strftime("%H:%M:%S", time.localtime())
        total_db_rows = sum(table_row_counts.values())
        
        # Create summary of table counts
        table_summary = ", ".join([f"{event_class}: {count}" for event_class, count in table_row_counts.items()])
        if not table_summary:
            table_summary = "No tables yet"
            
        print(f"\rLast update: {current_time} | Batch {last_batch_id}: {last_batch_size} records | "
              f"Total messages: {total_message_count} | Total VastDB rows: {total_db_rows} | "
              f"OCSF Classes: {len(processed_event_classes)} ({', '.join(sorted(processed_event_classes))}) | "
              f"Tables: [{table_summary}]     ", end="")
        
        import sys
        sys.stdout.flush()

# Helper function to create safe VastDB table names
def create_vastdb_table_name(event_class):
    """Create a VastDB table name for the OCSF event class"""
    # Clean up the event class for SQL compatibility
    clean_event_class = event_class.replace("-", "_").replace(".", "_")
    return f"`ndb`.`{VASTDB_FLUENTD_BUCKET}`.`{VASTDB_FLUENTD_SCHEMA}`.`{VASTDB_FLUENTD_TABLE_PREFIX}{clean_event_class}`"

# Helper function to create comprehensive OCSF schemas
def create_ocsf_schema(class_uid, class_name=None):
    """Create a comprehensive schema for OCSF event classes"""
    
    # Base OCSF fields that are common across all event classes
    base_fields = [
        # Core OCSF fields
        StructField("activity_id", StringType(), True),
        StructField("activity_name", StringType(), True),
        StructField("category_name", StringType(), True),
        StructField("category_uid", StringType(), True),
        StructField("class_name", StringType(), True),
        StructField("class_uid", StringType(), True),
        StructField("confidence", IntegerType(), True),
        StructField("count", IntegerType(), True),
        StructField("duration", IntegerType(), True),
        StructField("end_time", TimestampType(), True),
        StructField("end_time_dt", TimestampType(), True),
        StructField("message", StringType(), True),
        StructField("metadata", StringType(), True),  # JSON string for complex metadata
        StructField("observables", StringType(), True),  # Array of observables as JSON
        StructField("raw_data", StringType(), True),
        StructField("severity", StringType(), True),
        StructField("severity_id", StringType(), True),
        StructField("start_time", TimestampType(), True),
        StructField("start_time_dt", StringType(), True),
        StructField("status", StringType(), True),
        StructField("status_code", StringType(), True),
        StructField("status_detail", StringType(), True),
        StructField("status_id", StringType(), True),
        StructField("time", TimestampType(), True),
        StructField("time_dt", StringType(), True),
        StructField("timezone_offset", IntegerType(), True),
        StructField("type_name", StringType(), True),
        StructField("type_uid", StringType(), True),
        StructField("unmapped", StringType(), True),  # JSON string for unmapped fields
        
        # Actor fields
        StructField("actor_user_name", StringType(), True),
        StructField("actor_user_type", StringType(), True),
        StructField("actor_user_uid", StringType(), True),
        StructField("actor_user_email_addr", StringType(), True),
        StructField("actor_user_domain", StringType(), True),
        StructField("actor_session_uid", StringType(), True),
        StructField("actor_session_created_time", TimestampType(), True),
        StructField("actor_session_is_remote", BooleanType(), True),
        
        # Device fields  
        StructField("device_name", StringType(), True),
        StructField("device_type", StringType(), True),
        StructField("device_type_id", StringType(), True),
        StructField("device_uid", StringType(), True),
        StructField("device_hostname", StringType(), True),
        StructField("device_domain", StringType(), True),
        StructField("device_ip", StringType(), True),
        StructField("device_mac", StringType(), True),
        StructField("device_os_name", StringType(), True),
        StructField("device_os_version", StringType(), True),
        
        # Network endpoint fields
        StructField("src_endpoint_ip", StringType(), True),
        StructField("src_endpoint_port", IntegerType(), True),
        StructField("src_endpoint_hostname", StringType(), True),
        StructField("src_endpoint_domain", StringType(), True),
        StructField("src_endpoint_mac", StringType(), True),
        StructField("src_ip", StringType(), True),
        StructField("src_port", IntegerType(), True),
        StructField("dst_endpoint_ip", StringType(), True),
        StructField("dst_endpoint_port", IntegerType(), True),
        StructField("dst_endpoint_hostname", StringType(), True),
        StructField("dst_endpoint_domain", StringType(), True),
        StructField("dst_endpoint_mac", StringType(), True),
        StructField("dst_ip", StringType(), True),
        StructField("dst_port", IntegerType(), True),
        
        # Common user fields
        StructField("user", StringType(), True),
        StructField("user_name", StringType(), True),
        StructField("user_uid", StringType(), True),
        StructField("user_email_addr", StringType(), True),
        StructField("user_domain", StringType(), True),
        
        # Event specific fields based on your example
        StructField("event", StringType(), True),
        StructField("original_event_type", StringType(), True),
        
        # Product/Vendor fields
        StructField("ocsf_product_name", StringType(), True),
        StructField("ocsf_vendor_name", StringType(), True),
        StructField("ocsf_version", StringType(), True),
        
        # Additional fields from Fluentd (not standard OCSF but sent by our implementation)
        StructField("metadata_version", StringType(), True),
        StructField("metadata_product_name", StringType(), True),
        StructField("metadata_vendor_name", StringType(), True),
        StructField("metadata_product_version", StringType(), True),
        StructField("metadata_profiles", StringType(), True),
    ]
    
    # Add class-specific fields based on class_uid
    class_specific_fields = []
    
    if class_uid == "2004":  # Security Finding
        class_specific_fields.extend([
            StructField("finding_uid", StringType(), True),
            StructField("finding_title", StringType(), True),
            StructField("finding_desc", StringType(), True),
            StructField("finding_types", StringType(), True),  # Array as JSON string
            StructField("risk_level", StringType(), True),
            StructField("risk_level_id", StringType(), True),
            StructField("risk_score", DoubleType(), True),
            StructField("compliance_standards", StringType(), True), # Array as JSON string
        ])
    elif class_uid == "2001":  # Authentication
        class_specific_fields.extend([
            StructField("auth_protocol", StringType(), True),
            StructField("auth_protocol_id", StringType(), True),
            StructField("logon_type", StringType(), True),
            StructField("logon_type_id", StringType(), True),
            StructField("is_cleartext", BooleanType(), True),
            StructField("is_mfa", BooleanType(), True),
            StructField("is_new_logon", BooleanType(), True),
            StructField("is_remote", BooleanType(), True),
        ])
    elif class_uid == "3001":  # Network Activity
        class_specific_fields.extend([
            StructField("connection_uid", StringType(), True),
            StructField("direction", StringType(), True),
            StructField("direction_id", StringType(), True),
            StructField("protocol_name", StringType(), True),
            StructField("protocol_num", IntegerType(), True),
            StructField("session_uid", StringType(), True),
            StructField("bytes_in", LongType(), True),
            StructField("bytes_out", LongType(), True),
            StructField("packets_in", LongType(), True),
            StructField("packets_out", LongType(), True),
        ])
    elif class_uid == "3002":  # HTTP Activity  
        class_specific_fields.extend([
            StructField("http_method", StringType(), True),
            StructField("http_status", IntegerType(), True),
            StructField("http_response_code", IntegerType(), True),
            StructField("url_hostname", StringType(), True),
            StructField("url_path", StringType(), True),
            StructField("url_port", IntegerType(), True),
            StructField("url_query_string", StringType(), True),
            StructField("url_scheme", StringType(), True),
            StructField("user_agent", StringType(), True),
            StructField("referrer", StringType(), True),
            StructField("request_uid", StringType(), True),
            StructField("response_uid", StringType(), True),
        ])
    elif class_uid == "1007":  # Process Activity
        class_specific_fields.extend([
            StructField("process_name", StringType(), True),
            StructField("process_pid", IntegerType(), True),
            StructField("process_uid", StringType(), True),
            StructField("process_cmd_line", StringType(), True),
            StructField("process_file_name", StringType(), True),
            StructField("process_file_path", StringType(), True),
            StructField("parent_process_name", StringType(), True),
            StructField("parent_process_pid", IntegerType(), True),
            StructField("parent_process_uid", StringType(), True),
        ])
    
    # Combine base fields with class-specific fields
    all_fields = base_fields + class_specific_fields
    
    return StructType(all_fields)

# Helper function to determine event class from OCSF data
def determine_event_class(ocsf_data):
    """Determine the event class from OCSF data"""
    if "class_uid" in ocsf_data:
        class_uid = str(ocsf_data["class_uid"])
        class_name = OCSF_CLASS_MAPPING.get(class_uid)
        if class_name:
            return f"{class_uid}_{class_name}"
        else:
            return f"class_{class_uid}"
    elif "type_name" in ocsf_data:
        # Use type_name as fallback, clean it up
        type_name = ocsf_data["type_name"].lower().replace(" ", "_").replace("-", "_")
        return f"type_{type_name}"
    else:
        return "unknown_event"

# Helper function to convert timestamp columns to proper format
def convert_timestamp_columns(df, event_class):
    """Convert timestamp columns to proper TimestampType"""
    timestamp_columns = ["time", "time_dt", "start_time", "start_time_dt", "end_time", "end_time_dt", 
                        "actor_session_created_time"]
    
    for ts_col in timestamp_columns:
        if ts_col in df.columns:
            try:
                print(f"DEBUG - Converting timestamp column {ts_col} for event class {event_class}", flush=True)
                # Handle different timestamp formats
                if ts_col == "time":
                    # Handle Unix timestamp (integer seconds)
                    df = df.withColumn(ts_col, 
                        when(col(ts_col).isNotNull() & (col(ts_col) != "") & (col(ts_col) != "null"), 
                             from_unixtime(col(ts_col))
                        ).otherwise(None)
                    )
                elif ts_col.endswith("_dt"):
                    # Handle ISO timestamp strings (e.g., "2025-06-10T10:40:03.320Z")
                    # The time_dt field is already properly parsed from JSON as a string, just convert to timestamp
                    # Don't convert if it's already a timestamp - keep the original value
                    print(f"DEBUG - Converting {ts_col} for event class {event_class}", flush=True)
                    df = df.withColumn(ts_col, 
                        when(col(ts_col).isNotNull() & (col(ts_col) != "") & (col(ts_col) != "null"),
                             col(ts_col).cast(TimestampType())
                        ).otherwise(lit(None).cast(TimestampType()))
                    )
                    print(df)
                else:
                    # Handle other timestamp formats
                    df = df.withColumn(ts_col, 
                        when(col(ts_col).isNotNull() & (col(ts_col) != "") & (col(ts_col) != "null"), 
                             to_timestamp(col(ts_col))
                        ).otherwise(None)
                    )
            except Exception as e:
                print(f"Warning: Could not convert timestamp column {ts_col} for {event_class}: {e}")
    
    return df

# Helper function to create table schema in VastDB if it doesn't exist
def ensure_table_exists(event_class, sample_data):
    """Ensure the VastDB table exists for this OCSF event class with proper schema"""
    global created_tables
    
    table_name = create_vastdb_table_name(event_class)
    table_key = f"{VASTDB_FLUENTD_BUCKET}.{VASTDB_FLUENTD_SCHEMA}.{event_class}"
    
    if table_key not in created_tables:
        try:
            # Extract class_uid from the sample data to get appropriate schema
            sample_dict = json.loads(sample_data) if isinstance(sample_data, str) else sample_data
            class_uid = str(sample_dict.get("class_uid", "unknown"))
            
            # Get comprehensive schema for this class
            comprehensive_schema = create_ocsf_schema(class_uid)
            
            # Check if table exists by trying to query it
            try:
                existing_columns = spark.sql(f"DESCRIBE {table_name}").collect()
                existing_col_names = [row.col_name for row in existing_columns]
                expected_col_names = [field.name for field in comprehensive_schema.fields]
                
                # If the existing table doesn't have all the expected columns, recreate it
                missing_columns = set(expected_col_names) - set(existing_col_names)
                if missing_columns:
                    print(f"\nTable {table_name} exists but missing columns: {len(missing_columns)} columns")
                    print(f"Dropping and recreating table with comprehensive OCSF schema...")
                    
                    # Drop the existing table
                    spark.sql(f"DROP TABLE IF EXISTS {table_name}")
                    
                    # Create a sample DataFrame with the comprehensive schema
                    sample_data_list = [(None,) * len(comprehensive_schema.fields)]
                    sample_df = spark.createDataFrame(sample_data_list, comprehensive_schema)
                    sample_df.limit(0).write.mode("overwrite").saveAsTable(table_name)
                    print(f"Recreated table {table_name} with {len(comprehensive_schema.fields)} columns")
                
                created_tables.add(table_key)
                return table_name
                
            except Exception as e:
                # Table doesn't exist, create it with comprehensive schema
                try:
                    sample_data_list = [(None,) * len(comprehensive_schema.fields)]
                    sample_df = spark.createDataFrame(sample_data_list, comprehensive_schema)
                    sample_df.limit(0).write.mode("overwrite").saveAsTable(table_name)
                    print(f"\nCreated new OCSF table {table_name} for class_uid {class_uid} ({len(comprehensive_schema.fields)} columns)")
                    created_tables.add(table_key)
                    return table_name
                except Exception as create_error:
                    print(f"\nError creating table with comprehensive schema: {create_error}")
                    # Fall back to dynamic creation
                    created_tables.add(table_key)
                    return table_name
        except Exception as e:
            print(f"\nError in ensure_table_exists for {event_class}: {e}")
            created_tables.add(table_key)
            return table_name
    else:
        return create_vastdb_table_name(event_class)

# Process each microbatch with dynamic table routing based on OCSF event classes
def process_microbatch(raw_df, epoch_id):
    global total_message_count, last_batch_id, last_batch_size, processed_event_classes
    if not should_shutdown:
        try:
            batch_size = raw_df.count()
            # print(f"\n=== PROCESSING BATCH {epoch_id} with {batch_size} records ===")
            if batch_size == 0:
                print("Empty batch, skipping...")
                return
                
            total_message_count += batch_size
            last_batch_id = epoch_id
            last_batch_size = batch_size
            
            # Collect all JSON strings to determine event classes
            json_strings = [row.json for row in raw_df.collect()]
            # print(f"Collected {len(json_strings)} JSON strings from batch")
            
            # Group messages by event class
            event_class_groups = {}
            for json_str in json_strings:
                try:
                    parsed = json.loads(json_str)
                    event_class = determine_event_class(parsed)
                    processed_event_classes.add(event_class)
                    
                    if event_class not in event_class_groups:
                        event_class_groups[event_class] = []
                    event_class_groups[event_class].append(json_str)
                except Exception as e:
                    print(f"\nError parsing OCSF JSON: {e}")
                    continue
            
            # Process each event class group
            for event_class, json_list in event_class_groups.items():
                try:
                    # Create DataFrame for this event class
                    event_class_rdd = spark.sparkContext.parallelize([(json_str,) for json_str in json_list])
                    event_class_df = spark.createDataFrame(event_class_rdd, ["json"])
                    
                    # Parse the JSON directly (FluentD logs are flat JSON, not nested like Zeek)
                    sample_json = event_class_df.select("json").first()
                    if sample_json and sample_json.json:
                        try:
                            sample_dict = json.loads(sample_json.json)
                            class_uid = str(sample_dict.get("class_uid", "unknown"))
                            
                            # Get comprehensive OCSF schema
                            comprehensive_schema = create_ocsf_schema(class_uid)
                            
                            # Parse with comprehensive schema
                            parsed_df = event_class_df.select(
                                from_json(col("json"), comprehensive_schema).alias("parsed")
                            ).select("parsed.*")
                            
                            # Debug: Print column names and sample data
                            # print(f"\nDEBUG - Event class: {event_class}")
                            # print(f"DEBUG - DataFrame columns: {parsed_df.columns}")
                            if 'time_dt' in parsed_df.columns:
                                sample_time_dt = parsed_df.select('time_dt').first()
                                # print(f"DEBUG - Sample time_dt value BEFORE conversion: {sample_time_dt}")
                                # Show the actual string value
                                sample_time_dt_str = parsed_df.select('time_dt').collect()[0]['time_dt']
                                # print(f"DEBUG - Sample time_dt string value: '{sample_time_dt_str}'")
                            
                            # Convert timestamp columns
                            parsed_df = convert_timestamp_columns(parsed_df, event_class)
                            
                            # Debug: Check time_dt after conversion
                            if 'time_dt' in parsed_df.columns:
                                sample_time_dt_after = parsed_df.select('time_dt').first()
                                # print(f"DEBUG - Sample time_dt value AFTER conversion: {sample_time_dt_after}")
                            
                            # Ensure table exists and get table name
                            table_name = ensure_table_exists(event_class, sample_json.json)

                            # Create a new DataFrame with time_dt cast to TimestampType
                            parsed_df_ts = parsed_df.withColumn(
                                "time_dt",
                                when(col("time_dt").isNotNull() & (col("time_dt") != "") & (col("time_dt") != "null"),
                                     to_timestamp(col("time_dt"))
                                ).otherwise(lit(None).cast(TimestampType()))
                            )
                            
                            # Write to VastDB table specific to this event class with error handling
                            try:
                                parsed_df_ts.write.mode("append").saveAsTable(table_name)
                            except Exception as write_error:
                                if "Py4JNetworkError" in str(write_error) or "Answer from Java side is empty" in str(write_error):
                                    print(f"\nSpark connection error writing to {table_name}: {write_error}")
                                    time.sleep(2)
                                else:
                                    raise write_error
                                
                        except Exception as schema_error:
                            print(f"\nSchema processing error for {event_class}: {schema_error}")
                            # Fallback: store as raw JSON string
                            try:
                                fallback_df = event_class_df.select(col("json").alias("raw_json"))
                                table_name = f"`ndb`.`{VASTDB_FLUENTD_BUCKET}`.`{VASTDB_FLUENTD_SCHEMA}`.`{event_class}_raw`"
                                fallback_df.write.mode("append").saveAsTable(table_name)
                            except Exception as fallback_error:
                                print(f"\nFallback failed for {event_class}: {fallback_error}")
                
                except Exception as e:
                    print(f"\nError processing event class {event_class}: {e}")
                    continue
            
            print_status("Batch")
            
        except Exception as e:
            print(f"\nException in process_microbatch: {e}")

# Function to periodically check and update row counts for all VastDB tables
def check_row_counts():
    global table_row_counts, should_shutdown, processed_event_classes
    while not should_shutdown:
        time.sleep(3)  # Check every 3 seconds
        try:
            if should_shutdown:
                break
            # Create a copy of processed_event_classes to avoid modification during iteration
            event_classes_to_check = list(processed_event_classes)
            for event_class in event_classes_to_check:
                if should_shutdown:
                    break
                try:
                    table_name = create_vastdb_table_name(event_class)
                    # Add timeout and error handling for Spark SQL calls
                    new_count = spark.sql(f"SELECT count(*) FROM {table_name}").collect()[0][0]
                    if table_row_counts.get(event_class, 0) != new_count:
                        table_row_counts[event_class] = new_count
                        print_status("DB Count")
                except Exception as e:
                    # Table might not exist yet or be accessible, or Spark connection issues
                    if "Py4JNetworkError" in str(e) or "Answer from Java side is empty" in str(e):
                        print(f"\nSpark connection issue in row count check: {e}")
                        time.sleep(5)  # Wait longer before next attempt
                    pass
        except Exception as e:
            if should_shutdown:
                break
            # Ignore most errors in checking, but log network issues
            if "Py4JNetworkError" in str(e):
                print(f"\nNetwork error in check_row_counts: {e}")
                time.sleep(5)

# Read data from Kafka stream
raw_stream = spark.readStream \
    .format("kafka") \
    .option("kafka.bootstrap.servers", kafka_brokers) \
    .option("subscribe", topic) \
    .option("startingOffsets", "earliest") \
    .option("failOnDataLoss", "true") \
    .load()

# Decode Kafka messages as JSON strings
decoded_stream = raw_stream.selectExpr("CAST(value AS STRING) as json")

# Main processing query - using the dynamic approach for OCSF events
ocsf_query = decoded_stream.writeStream \
    .foreachBatch(process_microbatch) \
    .outputMode("append") \
    .trigger(processingTime='2 seconds') \
    .option("maxFilesPerTrigger", 1000) \
    .option("checkpointLocation", checkpoint_dir) \
    .start()

# Print initial status message
print("\nStarting FluentD OCSF log streaming job to VastDB...")
print("This will dynamically create VastDB tables for each OCSF event class (security_finding, authentication, etc.)")
print(f"Tables will be created in: ndb.{VASTDB_FLUENTD_BUCKET}.{VASTDB_FLUENTD_SCHEMA}")
print("All timestamp fields will be properly converted to TimestampType for optimal query performance.")
print("OCSF event classes will be automatically detected and routed to appropriate tables.")
print_status("Init")

# Start thread for checking row counts
row_count_thread = threading.Thread(target=check_row_counts)
row_count_thread.daemon = True
row_count_thread.start()

shutdown_flag = threading.Event()

def signal_handler(sig, frame):
    global should_shutdown
    print("\nGraceful shutdown initiated...")
    should_shutdown = True
    shutdown_flag.set()

signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)

# Main loop
try:
    while ocsf_query.isActive and not shutdown_flag.is_set():
        time.sleep(1)
    if ocsf_query.isActive:
        ocsf_query.stop()
    ocsf_query.awaitTermination()

except Exception as e:
    print(f"Error during awaitTermination: {e}")

print("\nFinal status:")
for event_class, count in table_row_counts.items():
    print(f"  {VASTDB_FLUENTD_BUCKET}.{VASTDB_FLUENTD_SCHEMA}.{VASTDB_FLUENTD_TABLE_PREFIX}{event_class}: {count} rows")
print("VastDB FluentD OCSF streaming completed. Goodbye!")
