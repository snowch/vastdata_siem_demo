#!/usr/bin/env python3
"""
Sample PySpark application demonstrating VastDB integration
"""

from pyspark.sql import SparkSession
from pyspark.sql.functions import *
import sys

def create_spark_session():
    """Create Spark session with VastDB configuration"""
    return SparkSession.builder \
        .appName("VastDB Integration Example") \
        .config("spark.sql.catalog.ndb", "spark.sql.catalog.ndb.VastCatalog") \
        .config("spark.sql.extensions", "ndb.NDBSparkSessionExtension") \
        .getOrCreate()

def list_databases(spark):
    """List available databases in VastDB"""
    print("=== Available Databases ===")
    databases = spark.sql("SHOW DATABASES")
    databases.show()
    return databases

def list_tables(spark, database="vastdb"):
    """List tables in a specific database"""
    print(f"=== Tables in {database} ===")
    try:
        tables = spark.sql(f"SHOW TABLES IN `ndb`.`{database}`")
        tables.show()
        return tables
    except Exception as e:
        print(f"Error listing tables in {database}: {e}")
        return None

def sample_query(spark, schema="schema1", table="table1"):
    """Execute a sample query on VastDB"""
    print(f"=== Sample Query: {schema}.{table} ===")
    try:
        # Query the table
        df = spark.sql(f"SELECT * FROM `ndb`.`vastdb`.`{schema}`.`{table}` LIMIT 10")
        print(f"Schema:")
        df.printSchema()
        print(f"Sample data:")
        df.show()
        
        # Get row count
        count = spark.sql(f"SELECT COUNT(*) as total_rows FROM `ndb`.`vastdb`.`{schema}`.`{table}`")
        count.show()
        
        return df
    except Exception as e:
        print(f"Error querying {schema}.{table}: {e}")
        return None

def data_analysis_example(spark, schema="schema1", table="table1"):
    """Demonstrate data analysis capabilities"""
    print(f"=== Data Analysis Example ===")
    try:
        # Create a temporary view
        spark.sql(f"""
            CREATE OR REPLACE TEMPORARY VIEW analysis_view AS
            SELECT * FROM `ndb`.`vastdb`.`{schema}`.`{table}`
        """)
        
        # Perform some analysis
        print("Column statistics:")
        stats = spark.sql("""
            SELECT 
                COUNT(*) as total_rows,
                COUNT(DISTINCT *) as distinct_rows
            FROM analysis_view
        """)
        stats.show()
        
        # If there are timestamp columns, show time-based analysis
        df = spark.table("analysis_view")
        columns = df.columns
        
        print(f"Available columns: {', '.join(columns)}")
        
        # Show first few rows with all columns
        print("Sample data with all columns:")
        df.limit(5).show(truncate=False)
        
    except Exception as e:
        print(f"Error in data analysis: {e}")

def main():
    """Main function"""
    print("Starting VastDB Integration Example")
    
    # Create Spark session
    spark = create_spark_session()
    
    try:
        # List databases
        list_databases(spark)
        
        # List tables in default database
        list_tables(spark, "vastdb")
        
        # Get command line arguments for schema and table
        schema = sys.argv[1] if len(sys.argv) > 1 else "schema1"
        table = sys.argv[2] if len(sys.argv) > 2 else "table1"
        
        print(f"Using schema: {schema}, table: {table}")
        
        # Execute sample query
        df = sample_query(spark, schema, table)
        
        if df is not None:
            # Perform data analysis
            data_analysis_example(spark, schema, table)
        
        print("Example completed successfully!")
        
    except Exception as e:
        print(f"Error in main execution: {e}")
        
    finally:
        # Stop Spark session
        spark.stop()

if __name__ == "__main__":
    main()
