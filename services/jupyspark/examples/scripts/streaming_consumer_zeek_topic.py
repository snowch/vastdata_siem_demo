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
        "KAFKA_BROKER": "Kafka broker address",
        "KAFKA_ZEEK_TOPIC": "Kafka Zeek topic name",
        "VASTDB_ZEEK_BUCKET": "VastDB Zeek bucket name",
        "VASTDB_ZEEK_SCHEMA": "VastDB Zeek schema name",
    }
    
    missing_vars = []
    env_values = {}
    
    # Check required variables
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
    
    # Set optional variables with defaults
    env_values["VASTDB_ZEEK_BUCKET"] = os.getenv("VASTDB_ZEEK_BUCKET", 'csnow-db')
    env_values["VASTDB_ZEEK_SCHEMA"] = os.getenv("VASTDB_ZEEK_SCHEMA", 'zeek-live-logs')
    env_values["KAFKA_ZEEK_TOPIC"] = os.getenv("KAFKA_ZEEK_TOPIC", 'zeek-live-logs')
    
    return env_values

# Validate and load environment variables
try:
    env_vars = validate_environment_variables()
    VASTDB_ENDPOINT = env_vars["VASTDB_ENDPOINT"]
    VASTDB_ACCESS_KEY = env_vars["VASTDB_ACCESS_KEY"] 
    VASTDB_SECRET_KEY = env_vars["VASTDB_SECRET_KEY"]
    VASTDB_ZEEK_BUCKET = env_vars["VASTDB_ZEEK_BUCKET"]
    VASTDB_ZEEK_SCHEMA = env_vars["VASTDB_ZEEK_SCHEMA"]
    KAFKA_BROKER = env_vars["KAFKA_BROKER"]
    topic = env_vars["KAFKA_ZEEK_TOPIC"]
except EnvironmentError as e:
    print(f"ERROR: {e}")
    sys.exit(1)

VASTDB_ZEEK_TABLE_PREFIX = '' # 'zeek_'

# Print configurations
print(f"""
---
VASTDB_ENDPOINT={VASTDB_ENDPOINT}
VASTDB_ACCESS_KEY=****{VASTDB_ACCESS_KEY[-4:]}
VASTDB_SECRET_KEY=****{VASTDB_SECRET_KEY[-4:]}
VASTDB_ZEEK_BUCKET={VASTDB_ZEEK_BUCKET}
VASTDB_ZEEK_SCHEMA={VASTDB_ZEEK_SCHEMA}
VASTDB_ZEEK_TABLE_PREFIX={VASTDB_ZEEK_TABLE_PREFIX}
---
KAFKA_BROKER={KAFKA_BROKER}
topic={topic}
""")

# Create Vast DB schema if it doesn't exist
import vastdb

session = vastdb.connect(endpoint=VASTDB_ENDPOINT, access=VASTDB_ACCESS_KEY, secret=VASTDB_SECRET_KEY)
with session.transaction() as tx:
    bucket = tx.bucket(VASTDB_ZEEK_BUCKET)
    bucket.schema(VASTDB_ZEEK_SCHEMA, fail_if_missing=False) or bucket.create_schema(VASTDB_ZEEK_SCHEMA)

import socket
import pyspark
from pyspark.conf import SparkConf
from pyspark.sql import SparkSession
from pyspark.sql.functions import from_json, col, count, get_json_object, to_timestamp, lit, when, isnan, isnull
from pyspark.sql.types import StructType, StructField, StringType, LongType, DoubleType, BooleanType, TimestampType, IntegerType
import threading
import time
import json
import signal

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
    .appName("ZeekStreamingToVastDB") \
    .config(conf=conf) \
    .enableHiveSupport() \
    .getOrCreate()

sc = spark.sparkContext
sc.setLogLevel("WARN")

print("Spark successfully loaded\n")

destination_table_name_prefix = f"`ndb`.`{VASTDB_ZEEK_BUCKET}`.`{VASTDB_ZEEK_SCHEMA}`.`{VASTDB_ZEEK_TABLE_PREFIX}`"
print(f"Table prefix: {destination_table_name_prefix}")

# Create checkpoint directory with absolute path
checkpoint_dir = os.path.abspath("/tmp/spark_zeek_checkpoint")
os.makedirs(checkpoint_dir, exist_ok=True)

# Global variables for tracking
total_message_count = 0
table_row_counts = {}  # Track row counts per table
last_batch_id = 0
last_batch_size = 0
processed_log_types = set()  # Track which log types we've seen
created_tables = set()  # Track which tables we've already created

should_shutdown = False

# Zeek log type to schema mapping
ZEEK_SCHEMAS = {
    'analyzer': StructType([
        StructField("ts", TimestampType(), True),
        StructField("cause", StringType(), True),
        StructField("analyzer_kind", StringType(), True),
        StructField("analyzer_name", StringType(), True),
        StructField("uid", StringType(), True),
        StructField("fuid", StringType(), True),
        StructField("id.orig_h", StringType(), True),
        StructField("id.orig_p", LongType(), True),
        StructField("id.resp_h", StringType(), True),
        StructField("id.resp_p", LongType(), True),
        StructField("failure_reason", StringType(), True),
        StructField("failure_data", StringType(), True),
    ]),
    'conn': StructType([
        StructField("ts", TimestampType(), True),
        StructField("uid", StringType(), True),
        StructField("id.orig_h", StringType(), True),
        StructField("id.orig_p", LongType(), True),
        StructField("id.resp_h", StringType(), True),
        StructField("id.resp_p", LongType(), True),
        StructField("proto", StringType(), True),
        StructField("service", StringType(), True),
        StructField("duration", DoubleType(), True),
        StructField("orig_bytes", LongType(), True),
        StructField("resp_bytes", LongType(), True),
        StructField("conn_state", StringType(), True),
        StructField("local_orig", BooleanType(), True),
        StructField("local_resp", BooleanType(), True),
        StructField("missed_bytes", LongType(), True),
        StructField("history", StringType(), True),
        StructField("orig_pkts", LongType(), True),
        StructField("orig_ip_bytes", LongType(), True),
        StructField("resp_pkts", LongType(), True),
        StructField("resp_ip_bytes", LongType(), True),
        StructField("ip_proto", StringType(), True),
        StructField("tunnel_parents", StringType(), True),
        StructField("vlan", LongType(), True),
        StructField("inner_vlan", LongType(), True),
        StructField("orig_l2_addr", StringType(), True),
        StructField("resp_l2_addr", StringType(), True),
        StructField("community_id", StringType(), True),
        StructField("orig_shim", StringType(), True),
        StructField("resp_shim", StringType(), True),
    ]),
    'http': StructType([
        StructField("ts", TimestampType(), True),
        StructField("uid", StringType(), True),
        StructField("id.orig_h", StringType(), True),
        StructField("id.orig_p", LongType(), True),
        StructField("id.resp_h", StringType(), True),
        StructField("id.resp_p", LongType(), True),
        StructField("trans_depth", LongType(), True),
        StructField("method", StringType(), True),
        StructField("host", StringType(), True),
        StructField("uri", StringType(), True),
        StructField("referrer", StringType(), True),
        StructField("version", StringType(), True),
        StructField("user_agent", StringType(), True),
        StructField("origin", StringType(), True),
        StructField("request_body_len", LongType(), True),
        StructField("response_body_len", LongType(), True),
        StructField("status_code", LongType(), True),
        StructField("status_msg", StringType(), True),
        StructField("info_code", LongType(), True),
        StructField("info_msg", StringType(), True),
        StructField("tags", StringType(), True),
        StructField("username", StringType(), True),
        StructField("password", StringType(), True),
        StructField("proxied", StringType(), True),
        StructField("orig_fuids", StringType(), True),
        StructField("orig_filenames", StringType(), True),
        StructField("orig_mime_types", StringType(), True),
        StructField("resp_fuids", StringType(), True),
        StructField("resp_filenames", StringType(), True),
        StructField("resp_mime_types", StringType(), True),
    ]),
    'dns': StructType([
        StructField("ts", TimestampType(), True),
        StructField("uid", StringType(), True),
        StructField("id.orig_h", StringType(), True),
        StructField("id.orig_p", LongType(), True),
        StructField("id.resp_h", StringType(), True),
        StructField("id.resp_p", LongType(), True),
        StructField("proto", StringType(), True),
        StructField("trans_id", LongType(), True),
        StructField("rtt", DoubleType(), True),
        StructField("query", StringType(), True),
        StructField("qclass", LongType(), True),
        StructField("qclass_name", StringType(), True),
        StructField("qtype", LongType(), True),
        StructField("qtype_name", StringType(), True),
        StructField("rcode", LongType(), True),
        StructField("rcode_name", StringType(), True),
        StructField("AA", BooleanType(), True),
        StructField("TC", BooleanType(), True),
        StructField("RD", BooleanType(), True),
        StructField("RA", BooleanType(), True),
        StructField("Z", LongType(), True),
        StructField("answers", StringType(), True),
        StructField("TTLs", StringType(), True),
        StructField("rejected", BooleanType(), True),
    ]),
    'ssl': StructType([
        StructField("ts", TimestampType(), True),
        StructField("uid", StringType(), True),
        StructField("id.orig_h", StringType(), True),
        StructField("id.orig_p", LongType(), True),
        StructField("id.resp_h", StringType(), True),
        StructField("id.resp_p", LongType(), True),
        StructField("version", StringType(), True),
        StructField("cipher", StringType(), True),
        StructField("curve", StringType(), True),
        StructField("server_name", StringType(), True),
        StructField("resumed", BooleanType(), True),
        StructField("last_alert", StringType(), True),
        StructField("next_protocol", StringType(), True),
        StructField("established", BooleanType(), True),
        StructField("cert_chain_fuids", StringType(), True),
        StructField("client_cert_chain_fuids", StringType(), True),
        StructField("subject", StringType(), True),
        StructField("issuer", StringType(), True),
        StructField("client_subject", StringType(), True),
        StructField("client_issuer", StringType(), True),
        StructField("validation_status", StringType(), True),
    ]),
    'weird': StructType([
        StructField("ts", TimestampType(), True),
        StructField("uid", StringType(), True),
        StructField("id.orig_h", StringType(), True),
        StructField("id.orig_p", LongType(), True),
        StructField("id.resp_h", StringType(), True),
        StructField("id.resp_p", LongType(), True),
        StructField("name", StringType(), True),
        StructField("addl", StringType(), True),
        StructField("notice", BooleanType(), True),
        StructField("peer", StringType(), True),
    ])
}

# Print a comprehensive status update
def print_status(source=""):
    global total_message_count, table_row_counts, last_batch_id, last_batch_size, processed_log_types
    if not should_shutdown:
        current_time = time.strftime("%H:%M:%S", time.localtime())
        total_db_rows = sum(table_row_counts.values())
        
        # Create summary of table counts
        table_summary = ", ".join([f"{log_type}: {count}" for log_type, count in table_row_counts.items()])
        if not table_summary:
            table_summary = "No tables yet"
            
        print(f"\rLast update: {current_time} | Batch {last_batch_id}: {last_batch_size} records | "
              f"Total messages: {total_message_count} | Total VastDB rows: {total_db_rows} | "
              f"Log types: {len(processed_log_types)} ({', '.join(sorted(processed_log_types))}) | "
              f"Tables: [{table_summary}]     ", end="")
        
        import sys
        sys.stdout.flush()

# Helper function to create safe VastDB table names
def create_vastdb_table_name(log_type):
    """Create a VastDB table name for the log type"""
    # Clean up the log type for SQL compatibility
    clean_log_type = log_type.replace("-", "_").replace(".", "_")
    return f"`ndb`.`{VASTDB_ZEEK_BUCKET}`.`{VASTDB_ZEEK_SCHEMA}`.`{VASTDB_ZEEK_TABLE_PREFIX}{clean_log_type}`"

# Helper function to create comprehensive schema for Zeek log types
def create_zeek_schema(log_type):
    """Create a comprehensive schema for the specified Zeek log type"""
    return ZEEK_SCHEMAS.get(log_type, None)

# Helper function to convert timestamp columns to proper format
def convert_timestamp_columns(df, log_type):
    """Convert timestamp columns to proper TimestampType"""
    if "ts" in df.columns:
        try:
            # Handle different timestamp formats that might be in Zeek logs
            df = df.withColumn("ts", 
                when(col("ts").isNotNull() & (col("ts") != ""), 
                     to_timestamp(col("ts"))
                ).otherwise(None)
            )
        except Exception as e:
            print(f"Warning: Could not convert timestamp column for {log_type}: {e}")
    
    return df

# Helper function to create table schema in VastDB if it doesn't exist
def ensure_table_exists(log_type, sample_data):
    """Ensure the VastDB table exists for this log type with proper schema"""
    global created_tables
    
    table_name = create_vastdb_table_name(log_type)
    table_key = f"{VASTDB_ZEEK_BUCKET}.{VASTDB_ZEEK_SCHEMA}.{log_type}"
    
    if table_key not in created_tables:
        try:
            # Get comprehensive schema for this log type
            comprehensive_schema = create_zeek_schema(log_type)
            
            # Check if table exists by trying to query it
            try:
                existing_columns = spark.sql(f"DESCRIBE {table_name}").collect()
                existing_col_names = [row.col_name for row in existing_columns]
                
                if comprehensive_schema:
                    expected_col_names = [field.name for field in comprehensive_schema.fields]
                    
                    # If the existing table doesn't have all the expected columns, recreate it
                    missing_columns = set(expected_col_names) - set(existing_col_names)
                    if missing_columns:
                        print(f"\nTable {table_name} exists but missing columns: {len(missing_columns)} columns")
                        print(f"Dropping and recreating table with comprehensive Zeek schema...")
                        
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
                    if comprehensive_schema:
                        sample_data_list = [(None,) * len(comprehensive_schema.fields)]
                        sample_df = spark.createDataFrame(sample_data_list, comprehensive_schema)
                        sample_df.limit(0).write.mode("overwrite").saveAsTable(table_name)
                        print(f"\nCreated new Zeek table {table_name} ({len(comprehensive_schema.fields)} columns)")
                    created_tables.add(table_key)
                    return table_name
                except Exception as create_error:
                    print(f"\nError creating table with comprehensive schema: {create_error}")
                    # Fall back to dynamic creation
                    created_tables.add(table_key)
                    return table_name
        except Exception as e:
            print(f"\nError in ensure_table_exists for {log_type}: {e}")
            created_tables.add(table_key)
            return table_name
    else:
        return create_vastdb_table_name(log_type)

# Process each microbatch with dynamic table routing based on Zeek log types
def process_microbatch(raw_df, epoch_id):
    global total_message_count, last_batch_id, last_batch_size, processed_log_types
    if not should_shutdown:
        try:
            batch_size = raw_df.count()
            if batch_size == 0:
                return
                
            total_message_count += batch_size
            last_batch_id = epoch_id
            last_batch_size = batch_size
            
            # Collect all JSON strings to determine log types
            json_strings = [row.json for row in raw_df.collect()]
            
            # Group messages by log type
            log_type_groups = {}
            for json_str in json_strings:
                try:
                    parsed = json.loads(json_str)
                    # Get the top-level key (log type)
                    log_type = list(parsed.keys())[0]
                    processed_log_types.add(log_type)
                    
                    if log_type not in log_type_groups:
                        log_type_groups[log_type] = []
                    log_type_groups[log_type].append(json_str)
                except Exception as e:
                    print(f"\nError parsing JSON: {e}")
                    continue
            
            # Process each log type group
            for log_type, json_list in log_type_groups.items():
                try:
                    # Create DataFrame for this log type
                    log_type_rdd = spark.sparkContext.parallelize([(json_str,) for json_str in json_list])
                    log_type_df = spark.createDataFrame(log_type_rdd, ["json"])
                    
                    # Extract the nested object for this log type using get_json_object
                    extracted_df = log_type_df.select(
                        get_json_object(col("json"), f"$.{log_type}").alias("log_data")
                    ).filter(col("log_data").isNotNull())
                    
                    if extracted_df.count() > 0:
                        # Use from_json with comprehensive or inferred schema
                        sample_json = extracted_df.select("log_data").first()
                        if sample_json and sample_json.log_data:
                            try:
                                # Try to use comprehensive schema first
                                comprehensive_schema = create_zeek_schema(log_type)
                                
                                if comprehensive_schema:
                                    # Use predefined comprehensive schema
                                    parsed_df = extracted_df.select(
                                        from_json(col("log_data"), comprehensive_schema).alias("parsed")
                                    ).select("parsed.*")
                                else:
                                    # Fall back to dynamic schema inference
                                    sample_dict = json.loads(sample_json.log_data)
                                    
                                    # Create a flexible schema that accommodates common types
                                    fields = []
                                    for key, value in sample_dict.items():
                                        if key == "ts" and isinstance(value, str):
                                            # For timestamp fields, start with StringType and convert later
                                            fields.append(StructField(key, StringType(), True))
                                        elif isinstance(value, str):
                                            fields.append(StructField(key, StringType(), True))
                                        elif isinstance(value, int):
                                            fields.append(StructField(key, LongType(), True))
                                        elif isinstance(value, float):
                                            fields.append(StructField(key, DoubleType(), True))
                                        elif isinstance(value, bool):
                                            fields.append(StructField(key, BooleanType(), True))
                                        else:
                                            # Default to string for complex types
                                            fields.append(StructField(key, StringType(), True))
                                    
                                    inferred_schema = StructType(fields)
                                    
                                    # Parse with inferred schema
                                    parsed_df = extracted_df.select(
                                        from_json(col("log_data"), inferred_schema).alias("parsed")
                                    ).select("parsed.*")
                                
                                # Convert timestamp columns
                                parsed_df = convert_timestamp_columns(parsed_df, log_type)
                                
                                # Ensure table exists and get table name
                                table_name = ensure_table_exists(log_type, sample_json.log_data)
                                
                                # Write to VastDB table specific to this log type with error handling
                                try:
                                    parsed_df.write.mode("append").saveAsTable(table_name)
                                except Exception as write_error:
                                    if "Py4JNetworkError" in str(write_error) or "Answer from Java side is empty" in str(write_error):
                                        print(f"\nSpark connection error writing to {table_name}: {write_error}")
                                        time.sleep(2)
                                    else:
                                        raise write_error
                                        
                            except Exception as schema_error:
                                print(f"\nSchema processing error for {log_type}: {schema_error}")
                                # Fallback: store as raw JSON string
                                try:
                                    fallback_df = extracted_df.select(col("log_data").alias("raw_json"))
                                    table_name = f"`ndb`.`{VASTDB_ZEEK_BUCKET}`.`{VASTDB_ZEEK_SCHEMA}`.`{log_type}_raw`"
                                    fallback_df.write.mode("append").saveAsTable(table_name)
                                except Exception as fallback_error:
                                    print(f"\nFallback failed for {log_type}: {fallback_error}")
                
                except Exception as e:
                    print(f"\nError processing log type {log_type}: {e}")
                    continue
            
            print_status("Batch")
            
        except Exception as e:
            print(f"\nException in process_microbatch: {e}")

# Function to periodically check and update row counts for all VastDB tables
def check_row_counts():
    global table_row_counts, should_shutdown, processed_log_types
    while not should_shutdown:
        time.sleep(3)  # Check every 3 seconds
        try:
            if should_shutdown:
                break
            # Create a copy of processed_log_types to avoid modification during iteration
            log_types_to_check = list(processed_log_types)
            for log_type in log_types_to_check:
                if should_shutdown:
                    break
                try:
                    table_name = create_vastdb_table_name(log_type)
                    # Add timeout and error handling for Spark SQL calls
                    new_count = spark.sql(f"SELECT count(*) FROM {table_name}").collect()[0][0]
                    if table_row_counts.get(log_type, 0) != new_count:
                        table_row_counts[log_type] = new_count
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
    .option("kafka.bootstrap.servers", KAFKA_BROKER) \
    .option("subscribe", topic) \
    .option("startingOffsets", "earliest") \
    .option("failOnDataLoss", "true") \
    .load()

# Decode Kafka messages as JSON strings
decoded_stream = raw_stream.selectExpr("CAST(value AS STRING) as json")

# Main processing query - using the dynamic approach for Zeek logs
zeek_query = decoded_stream.writeStream \
    .foreachBatch(process_microbatch) \
    .outputMode("append") \
    .trigger(processingTime='2 seconds') \
    .option("maxFilesPerTrigger", 1000) \
    .option("checkpointLocation", checkpoint_dir) \
    .start()

# Print initial status message
print("\nStarting Zeek log streaming job to VastDB...")
print("This will dynamically create VastDB tables for each Zeek log type (conn, http, dns, ssl, etc.)")
print(f"Tables will be created in: ndb.{VASTDB_ZEEK_BUCKET}.{VASTDB_ZEEK_SCHEMA}")
print("All timestamp fields will be properly converted to TimestampType for optimal query performance.")
print("Zeek log types will be automatically detected and routed to appropriate tables.")
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
    while zeek_query.isActive and not shutdown_flag.is_set():
        time.sleep(1)
    if zeek_query.isActive:
        zeek_query.stop()
    zeek_query.awaitTermination()

except Exception as e:
    print(f"Error during awaitTermination: {e}")

print("\nFinal status:")
for log_type, count in table_row_counts.items():
    print(f"  {VASTDB_ZEEK_BUCKET}.{VASTDB_ZEEK_SCHEMA}.{VASTDB_ZEEK_TABLE_PREFIX}{log_type}: {count} rows")
print("VastDB Zeek streaming completed. Goodbye!")