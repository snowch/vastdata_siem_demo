#!/usr/bin/env python

import os

# Load environment variables for Kafka and VastDB connectivity

VASTDB_ENDPOINT = os.getenv("VASTDB_ENDPOINT")
VASTDB_ACCESS_KEY = os.getenv("VASTDB_ACCESS_KEY")
VASTDB_SECRET_KEY = os.getenv("VASTDB_SECRET_KEY")

VASTDB_SIEM_BUCKET = os.getenv("VASTDB_SIEM_BUCKET", 'csnow-db')
VASTDB_SIEM_SCHEMA = os.getenv("VASTDB_SIEM_SCHEMA", 'zeek-live-logs')
VASTDB_SIEM_TABLE_PREFIX = 'zeek_'

use_vastkafka = True
if use_vastkafka:
    VAST_KAFKA_BROKER = os.getenv("VAST_KAFKA_BROKER")
else:
    VAST_KAFKA_BROKER = f"{DOCKER_HOST_OR_IP}:19092"

kafka_brokers = VAST_KAFKA_BROKER
topic = 'zeek-live-logs'

# Print configurations
print(f"""
---
VASTDB_ENDPOINT={VASTDB_ENDPOINT}
VASTDB_ACCESS_KEY==****{VASTDB_ACCESS_KEY[-4:]}
VASTDB_SECRET_KEY=****{VASTDB_SECRET_KEY[-4:]}
VASTDB_SIEM_BUCKET={VASTDB_SIEM_BUCKET}
VASTDB_SIEM_SCHEMA={VASTDB_SIEM_SCHEMA}
VASTDB_SIEM_TABLE_PREFIX={VASTDB_SIEM_TABLE_PREFIX}
---
VAST_KAFKA_BROKER={VAST_KAFKA_BROKER}
topic={topic}
""")


import vastdb

session = vastdb.connect(endpoint=VASTDB_ENDPOINT, access=VASTDB_ACCESS_KEY, secret=VASTDB_SECRET_KEY)
with session.transaction() as tx:
    bucket = tx.bucket(VASTDB_SIEM_BUCKET)
    bucket.schema(VASTDB_SIEM_SCHEMA, fail_if_missing=False) or bucket.create_schema(VASTDB_SIEM_SCHEMA)


# In[4]:


import socket
import pyspark
from pyspark.conf import SparkConf
from pyspark.sql import SparkSession
from pyspark.sql.functions import from_json, col, count, get_json_object, to_timestamp
from pyspark.sql.types import StructType, StructField, StringType, LongType, DoubleType, BooleanType, TimestampType
import threading
import time
import json  # <-- MISSING IMPORT ADDED HERE

# Spark Configuration
conf = SparkConf()
conf.setAll([
    ("spark.driver.host", socket.gethostbyname(socket.gethostname())),
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
    ("spark.hadoop.fs.file.impl", "org.apache.hadoop.fs.RawLocalFileSystem"),
])

spark = SparkSession.builder \
    .master("local") \
    .appName("KafkaStreamingToVastDB") \
    .config(conf=conf) \
    .enableHiveSupport() \
    .getOrCreate()

sc = spark.sparkContext
sc.setLogLevel("DEBUG")

print("Spark successfully loaded\n")


# In[5]:


destination_table_name_prefix = f"`ndb`.`{VASTDB_SIEM_BUCKET}`.`{VASTDB_SIEM_SCHEMA}`.`{VASTDB_SIEM_TABLE_PREFIX}`"
destination_table_name_prefix


# In[6]:


import os
import signal
import time
import threading
import pyspark
from pyspark.sql.functions import col, from_json
from pyspark.sql.types import *

# Create checkpoint directory with absolute path
checkpoint_dir = os.path.abspath("/tmp/spark_checkpoint")
os.makedirs(checkpoint_dir, exist_ok=True)

# Global variables for tracking
total_message_count = 0
table_row_counts = {}  # Track row counts per table
last_batch_id = 0
last_batch_size = 0
processed_log_types = set()  # Track which log types we've seen
created_tables = set()  # Track which tables we've already created

should_shutdown = False

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
    return f"`ndb`.`{VASTDB_SIEM_BUCKET}`.`{VASTDB_SIEM_SCHEMA}`.`{clean_log_type}`"

# Helper function to create comprehensive schema for Zeek log types
def create_comprehensive_schema(log_type):
    """Create a comprehensive schema that includes all possible fields for a log type"""
    
    # Define comprehensive schemas for common Zeek log types with proper TimestampType
    zeek_schemas = {
        'analyzer': StructType([
            StructField("ts", TimestampType(), True),
            StructField("cause", StringType(), True),
            StructField("analyzer_kind", StringType(), True),
            StructField("analyzer_name", StringType(), True),
            StructField("uid", StringType(), True),  # Optional field
            StructField("fuid", StringType(), True),  # Optional field
            StructField("id.orig_h", StringType(), True),  # Optional field from conn_id
            StructField("id.orig_p", LongType(), True),  # Optional field from conn_id
            StructField("id.resp_h", StringType(), True),  # Optional field from conn_id
            StructField("id.resp_p", LongType(), True),  # Optional field from conn_id
            StructField("failure_reason", StringType(), True),  # Optional field
            StructField("failure_data", StringType(), True),  # Optional field
        ]),
        'conn': StructType([
            StructField("ts", TimestampType(), True),
            StructField("uid", StringType(), True),
            StructField("id.orig_h", StringType(), True),
            StructField("id.orig_p", LongType(), True),
            StructField("id.resp_h", StringType(), True),
            StructField("id.resp_p", LongType(), True),
            StructField("proto", StringType(), True),
            StructField("service", StringType(), True),  # Optional field
            StructField("duration", DoubleType(), True),  # Optional field
            StructField("orig_bytes", LongType(), True),  # Optional field
            StructField("resp_bytes", LongType(), True),  # Optional field
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
            StructField("tunnel_parents", StringType(), True),  # Optional field
            # Additional common Zeek conn.log fields
            StructField("vlan", LongType(), True),  # VLAN tag
            StructField("inner_vlan", LongType(), True),  # Inner VLAN tag
            StructField("orig_l2_addr", StringType(), True),  # Original L2 address
            StructField("resp_l2_addr", StringType(), True),  # Responder L2 address
            StructField("community_id", StringType(), True),  # Community ID hash
            StructField("orig_shim", StringType(), True),  # Original shim header
            StructField("resp_shim", StringType(), True),  # Responder shim header
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
    
    # Return predefined schema if available, otherwise return None for dynamic inference
    return zeek_schemas.get(log_type, None)

# Helper function to convert timestamp string to proper format
def convert_timestamp_column(df, log_type):
    """Convert timestamp string to proper TimestampType"""
    if "ts" in df.columns:
        # Handle different timestamp formats that might be in Zeek logs
        try:
            # Try ISO format first: "2025-05-31T20:53:25.978455Z"
            df = df.withColumn("ts", to_timestamp(col("ts"), "yyyy-MM-dd'T'HH:mm:ss.SSSSSS'Z'"))
        except:
            try:
                # Try without microseconds: "2025-05-31T20:53:25.978Z"
                df = df.withColumn("ts", to_timestamp(col("ts"), "yyyy-MM-dd'T'HH:mm:ss.SSS'Z'"))
            except:
                try:
                    # Try basic ISO format
                    df = df.withColumn("ts", to_timestamp(col("ts")))
                except:
                    print(f"Warning: Could not convert timestamp for {log_type}, keeping as string")
    return df

# Helper function to create table schema in VastDB if it doesn't exist
def ensure_table_exists(log_type, sample_data):
    """Ensure the VastDB table exists for this log type with proper schema"""
    global created_tables
    
    table_name = create_vastdb_table_name(log_type)
    table_key = f"{VASTDB_SIEM_BUCKET}.{VASTDB_SIEM_SCHEMA}.{log_type}"
    
    # Check if we have a comprehensive schema for this log type
    comprehensive_schema = create_comprehensive_schema(log_type)
    
    if comprehensive_schema and table_key not in created_tables:
        try:
            # Check if table exists by trying to query it
            existing_columns = spark.sql(f"DESCRIBE {table_name}").collect()
            existing_col_names = [row.col_name for row in existing_columns]
            expected_col_names = [field.name for field in comprehensive_schema.fields]
            
            # If the existing table doesn't have all the expected columns, we need to recreate it
            missing_columns = set(expected_col_names) - set(existing_col_names)
            if missing_columns:
                print(f"\nTable {table_name} exists but missing columns: {missing_columns}")
                print(f"Dropping and recreating table with comprehensive schema...")
                
                # Drop the existing table
                spark.sql(f"DROP TABLE IF EXISTS {table_name}")
                
                # Create a sample DataFrame with the comprehensive schema to create the table
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
                print(f"\nCreated new table {table_name} with comprehensive schema ({len(comprehensive_schema.fields)} columns)")
                created_tables.add(table_key)
                return table_name
            except Exception as create_error:
                print(f"\nError creating table with comprehensive schema: {create_error}")
                # Fall back to dynamic creation
                created_tables.add(table_key)
                return table_name
    else:
        # No comprehensive schema available or already created, use existing logic
        if table_key in created_tables:
            return table_name
        
        try:
            # Try to query the table to see if it exists
            spark.sql(f"SELECT 1 FROM {table_name} LIMIT 1")
            created_tables.add(table_key)
            return table_name
        except:
            # Table doesn't exist, we'll let Spark create it dynamically
            created_tables.add(table_key)
            return table_name

# Process each microbatch with dynamic table routing and timestamp conversion
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
                                comprehensive_schema = create_comprehensive_schema(log_type)
                                
                                if comprehensive_schema:
                                    # Use predefined comprehensive schema
                                    parsed_df = extracted_df.select(
                                        from_json(col("log_data"), comprehensive_schema).alias("parsed")
                                    ).select("parsed.*")
                                    
                                    # Convert timestamp column for predefined schemas
                                    parsed_df = convert_timestamp_column(parsed_df, log_type)
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
                                    
                                    # Convert timestamp column for dynamic schemas
                                    parsed_df = convert_timestamp_column(parsed_df, log_type)
                                
                                # Ensure table exists and get table name
                                table_name = ensure_table_exists(log_type, sample_json.log_data)
                                
                                # Write to VastDB table specific to this log type with error handling
                                try:
                                    parsed_df.write.mode("append").saveAsTable(table_name)
                                except Exception as write_error:
                                    if "Py4JNetworkError" in str(write_error) or "Answer from Java side is empty" in str(write_error):
                                        print(f"\nSpark connection error writing to {table_name}: {write_error}")
                                        # Try to reconnect or handle gracefully
                                        time.sleep(2)
                                    else:
                                        raise write_error
                                
                            except Exception as schema_error:
                                print(f"\nSchema inference error for {log_type}: {schema_error}")
                                # Fallback: store as raw JSON string
                                try:
                                    fallback_df = extracted_df.select(col("log_data").alias("raw_json"))
                                    table_name = f"`ndb`.`{VASTDB_SIEM_BUCKET}`.`{VASTDB_SIEM_SCHEMA}`.`{log_type}_raw`"
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
    .option("kafka.bootstrap.servers", kafka_brokers) \
    .option("subscribe", topic) \
    .option("startingOffsets", "earliest") \
    .option("failOnDataLoss", "true") \
    .load()

# Decode Kafka messages as JSON strings
decoded_stream = raw_stream.selectExpr("CAST(value AS STRING) as json")

# Main processing query - using the dynamic approach
zeek_query = decoded_stream.writeStream \
    .foreachBatch(process_microbatch) \
    .outputMode("append") \
    .trigger(processingTime='2 seconds') \
    .option("maxFilesPerTrigger", 1000) \
    .option("checkpointLocation", checkpoint_dir) \
    .start()

# Print initial status message
print("\nStarting Zeek log streaming job to VastDB...")
print("This will dynamically create VastDB tables for each Zeek log type (conn, analyzer, weird, etc.)")
print(f"Tables will be created in: ndb.{VASTDB_SIEM_BUCKET}.{VASTDB_SIEM_SCHEMA}")
print("All timestamp fields will be properly converted to TimestampType for optimal query performance.")
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
    print(f"  {VASTDB_SIEM_BUCKET}.{VASTDB_SIEM_SCHEMA}.{log_type}: {count} rows")
print("VastDB Zeek streaming completed. Goodbye!")


# In[ ]: .. see ocsf_streaming.py as an example of integration