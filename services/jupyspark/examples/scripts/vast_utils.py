#!/usr/bin/env python

import os
import sys
import socket
import vastdb
from pyspark.conf import SparkConf
from pyspark.sql import SparkSession

def validate_environment_variables():
    """Validate that all required environment variables are set"""
    required_env_vars = {
        "VASTDB_ENDPOINT": "VastDB endpoint URL",
        "VASTDB_ACCESS_KEY": "VastDB access key", 
        "VASTDB_SECRET_KEY": "VastDB secret key",
        "KAFKA_BROKER": "Kafka broker address",
        "KAFKA_ZEEK_TOPIC": "Kafka Zeek topic name",
        "KAFKA_EVENT_LOG_TOPIC": "Kafka FluentD topic name",
        "VASTDB_ZEEK_BUCKET": "VastDB Zeek bucket name",
        "VASTDB_ZEEK_SCHEMA": "VastDB Zeek schema name",
        "VASTDB_ZEEK_TABLE_PREFIX": "VastDB Zeek table prefix",
        "VASTDB_FLUENTD_BUCKET": "VastDB FluentD bucket name",
        "VASTDB_FLUENTD_SCHEMA": "VastDB FluentD schema name", 
        "VASTDB_FLUENTD_TABLE_PREFIX": "VastDB FluentD table prefix",
    }
    
    missing_vars = []
    env_values = {}
    
    # Check all required variables
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

def print_configuration(env_vars):
    """Print the current configuration"""
    print(f"""
Configuration:
---
KAFKA_BROKER={env_vars['KAFKA_BROKER']}
KAFKA_ZEEK_TOPIC={env_vars['KAFKA_ZEEK_TOPIC']}
KAFKA_EVENT_LOG_TOPIC={env_vars['KAFKA_EVENT_LOG_TOPIC']}
---
VASTDB_ENDPOINT={env_vars['VASTDB_ENDPOINT']}
VASTDB_ACCESS_KEY=****{env_vars['VASTDB_ACCESS_KEY'][-4:]}
VASTDB_SECRET_KEY=****{env_vars['VASTDB_SECRET_KEY'][-4:]}
VASTDB_ZEEK_BUCKET={env_vars['VASTDB_ZEEK_BUCKET']}
VASTDB_ZEEK_SCHEMA={env_vars['VASTDB_ZEEK_SCHEMA']}
VASTDB_ZEEK_TABLE_PREFIX={env_vars['VASTDB_ZEEK_TABLE_PREFIX']}
VASTDB_FLUENTD_BUCKET={env_vars['VASTDB_FLUENTD_BUCKET']}
VASTDB_FLUENTD_SCHEMA={env_vars['VASTDB_FLUENTD_SCHEMA']}
VASTDB_FLUENTD_TABLE_PREFIX={env_vars['VASTDB_FLUENTD_TABLE_PREFIX']}
---
""")

def create_vastdb_schema(env_vars):
    """Create VastDB schema if it doesn't exist"""
    session = vastdb.connect(
        endpoint=env_vars['VASTDB_ENDPOINT'], 
        access=env_vars['VASTDB_ACCESS_KEY'], 
        secret=env_vars['VASTDB_SECRET_KEY']
    )
    
    with session.transaction() as tx:
        # Create Zeek schema
        bucket = tx.bucket(env_vars['VASTDB_ZEEK_BUCKET'])
        bucket.schema(env_vars['VASTDB_ZEEK_SCHEMA'], fail_if_missing=False) or bucket.create_schema(env_vars['VASTDB_ZEEK_SCHEMA'])
        
        # Create FluentD schema if different bucket/schema
        if (env_vars['VASTDB_FLUENTD_BUCKET'] != env_vars['VASTDB_ZEEK_BUCKET'] or 
            env_vars['VASTDB_FLUENTD_SCHEMA'] != env_vars['VASTDB_ZEEK_SCHEMA']):
            fluentd_bucket = tx.bucket(env_vars['VASTDB_FLUENTD_BUCKET'])
            fluentd_bucket.schema(env_vars['VASTDB_FLUENTD_SCHEMA'], fail_if_missing=False) or fluentd_bucket.create_schema(env_vars['VASTDB_FLUENTD_SCHEMA'])

def get_spark_session(app_name="ZeekStreamingToVastDB", print_config=True):
    """
    Create and return a configured Spark session for VastDB and Kafka integration.
    
    Args:
        app_name (str): Name for the Spark application
        print_config (bool): Whether to print configuration details
    
    Returns:
        tuple: (SparkSession, env_vars dict)
    """
    try:
        # Validate and load environment variables
        env_vars = validate_environment_variables()
        
        if print_config:
            print_configuration(env_vars)
        
        # Create VastDB schemas
        create_vastdb_schema(env_vars)
        
        # Spark Configuration
        conf = SparkConf()
        conf.setAll([
            ("spark.sql.execution.arrow.pyspark.enabled", "false"),
            # VastDB Configuration
            ("spark.sql.catalog.ndb", 'spark.sql.catalog.ndb.VastCatalog'),
            ("spark.ndb.endpoint", env_vars['VASTDB_ENDPOINT']),
            ("spark.ndb.data_endpoints", env_vars['VASTDB_ENDPOINT']),
            ("spark.ndb.access_key_id", env_vars['VASTDB_ACCESS_KEY']),
            ("spark.ndb.secret_access_key", env_vars['VASTDB_SECRET_KEY']),
            ("spark.driver.extraClassPath", '/usr/local/spark/jars/spark3-vast-3.4.1-f93839bfa38a/*'),
            ("spark.executor.extraClassPath", '/usr/local/spark/jars/spark3-vast-3.4.1-f93839bfa38a/*'),
            ("spark.sql.extensions", 'ndb.NDBSparkSessionExtension'),
            # Kafka Configuration
            ("spark.jars.packages", "org.apache.spark:spark-sql-kafka-0-10_2.13:3.4.3," 
                                    "org.apache.logging.log4j:log4j-slf4j2-impl:2.19.0," 
                                    "org.apache.logging.log4j:log4j-api:2.19.0," 
                                    "org.apache.logging.log4j:log4j-core:2.19.0"),
            ("spark.jars.excludes", "org.slf4j:slf4j-api,org.slf4j:slf4j-log4j12"),
        ])
        
        # Create Spark session
        spark = SparkSession.builder \
            .appName(app_name) \
            .config(conf=conf) \
            .enableHiveSupport() \
            .getOrCreate()
        
        # Set log level
        spark.sparkContext.setLogLevel("WARN")
        
        if print_config:
            print("✓ Spark session successfully created")
            
            # Print table prefixes for convenience
            zeek_table_prefix = f"`ndb`.`{env_vars['VASTDB_ZEEK_BUCKET']}`.`{env_vars['VASTDB_ZEEK_SCHEMA']}`.`{env_vars['VASTDB_ZEEK_TABLE_PREFIX']}`"
            fluentd_table_prefix = f"`ndb`.`{env_vars['VASTDB_FLUENTD_BUCKET']}`.`{env_vars['VASTDB_FLUENTD_SCHEMA']}`.`{env_vars['VASTDB_FLUENTD_TABLE_PREFIX']}`"
            
            print(f"✓ Zeek table prefix: {zeek_table_prefix}")
            print(f"✓ FluentD table prefix: {fluentd_table_prefix}")
            print()
        
        return spark, env_vars
        
    except EnvironmentError as e:
        print(f"ERROR: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"ERROR creating Spark session: {e}")
        sys.exit(1)

def get_table_name(env_vars, table_type, table_name):
    """
    Helper function to construct full table names.
    
    Args:
        env_vars (dict): Environment variables dictionary
        table_type (str): Either 'zeek' or 'fluentd'
        table_name (str): Base table name
    
    Returns:
        str: Full table name with catalog, bucket, schema, and prefix
    """
    if table_type.lower() == 'zeek':
        return f"`ndb`.`{env_vars['VASTDB_ZEEK_BUCKET']}`.`{env_vars['VASTDB_ZEEK_SCHEMA']}`.`{env_vars['VASTDB_ZEEK_TABLE_PREFIX']}{table_name}`"
    elif table_type.lower() == 'fluentd':
        return f"`ndb`.`{env_vars['VASTDB_FLUENTD_BUCKET']}`.`{env_vars['VASTDB_FLUENTD_SCHEMA']}`.`{env_vars['VASTDB_FLUENTD_TABLE_PREFIX']}{table_name}`"
    else:
        raise ValueError("table_type must be either 'zeek' or 'fluentd'")

def display_dataframe(df, num_rows=5, use_pandas=True, truncate=True):
    """
    Display DataFrame in a notebook-friendly format.
    
    Args:
        df: Spark DataFrame
        num_rows (int): Number of rows to display
        use_pandas (bool): Convert to pandas for better notebook display
        truncate (bool): Whether to truncate long values
    """
    if use_pandas:
        try:
            import pandas as pd
            
            # Handle timestamp conversion issues by converting to string first
            from pyspark.sql.functions import col, date_format
            from pyspark.sql.types import TimestampType
            
            # Convert timestamp columns to strings to avoid conversion errors
            timestamp_cols = [field.name for field in df.schema.fields if isinstance(field.dataType, TimestampType)]
            
            if timestamp_cols:
                print(f"Note: Converting timestamp columns to strings for display: {timestamp_cols}")
                for ts_col in timestamp_cols:
                    df = df.withColumn(ts_col, date_format(col(ts_col), "yyyy-MM-dd HH:mm:ss.SSS"))
            
            pandas_df = df.limit(num_rows).toPandas()
            if not truncate:
                pd.set_option('display.max_colwidth', None)
                pd.set_option('display.width', None)
                pd.set_option('display.max_columns', None)
            return pandas_df
            
        except Exception as e:
            print(f"Pandas conversion failed ({str(e)}), falling back to Spark display")
            df.show(num_rows, truncate=truncate)
            return None
    else:
        df.show(num_rows, truncate=truncate)
        return None

def safe_show(df, num_rows=5, truncate=True):
    """
    Safe way to display Spark DataFrame using native Spark .show() method.
    
    Args:
        df: Spark DataFrame
        num_rows (int): Number of rows to display  
        truncate (bool): Whether to truncate long values
    """
    df.show(num_rows, truncate=truncate)

# For direct script execution
if __name__ == "__main__":
    spark, env_vars = get_spark_session()
    
    # Example usage
    print("Example table names:")
    print(f"Zeek conn table: {get_table_name(env_vars, 'zeek', 'conn')}")
    print(f"FluentD logs table: {get_table_name(env_vars, 'fluentd', 'logs')}")