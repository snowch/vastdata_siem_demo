#!/bin/bash

# PySpark Helper Script
# Provides convenient commands for common Spark operations

SPARK_MASTER="spark://spark-master:7077"
SPARK_CLIENT="spark-client"

# Function to display usage
usage() {
    echo "Usage: $0 [COMMAND]"
    echo ""
    echo "Commands:"
    echo "  sql         - Start Spark SQL interactive session"
    echo "  pyspark     - Start PySpark interactive session"
    echo "  submit FILE - Submit a Spark application"
    echo "  status      - Show cluster status"
    echo "  logs        - Show Spark logs"
    echo "  help        - Show this help message"
    echo ""
    echo "Examples:"
    echo "  $0 sql"
    echo "  $0 pyspark"
    echo "  $0 submit /path/to/app.py"
    echo "  $0 status"
}

# Function to start Spark SQL
start_sql() {
    echo "Starting Spark SQL session..."
    docker exec -it $SPARK_CLIENT /opt/spark/bin/spark-sql \
        --master $SPARK_MASTER \
        --driver-class-path $(echo '/opt/spark/vast/*.jar' | tr ' ' ':') \
        --conf spark.executor.extraClassPath=$(echo '/opt/spark/vast/*.jar' | tr ' ' ':') \
        --jars $(echo '/opt/spark/vast/*.jar' | tr ' ' ',') \
        --conf spark.executor.userClassPathFirst=true \
        --conf spark.driver.userClassPathFirst=true \
        --conf spark.driver.maxResultSize=4g \
        --conf spark.driver.memory=16g \
        --conf spark.executor.cores=8 \
        --conf spark.executor.memory=8g \
        --conf spark.sql.catalogImplementation=in-memory
}

# Function to start PySpark
start_pyspark() {
    echo "Starting PySpark session..."
    docker exec -it $SPARK_CLIENT /opt/spark/bin/pyspark \
        --master $SPARK_MASTER \
        --driver-class-path $(echo '/opt/spark/vast/*.jar' | tr ' ' ':') \
        --conf spark.executor.extraClassPath=$(echo '/opt/spark/vast/*.jar' | tr ' ' ':') \
        --jars $(echo '/opt/spark/vast/*.jar' | tr ' ' ',') \
        --conf spark.executor.userClassPathFirst=true \
        --conf spark.driver.userClassPathFirst=true
}

# Function to submit Spark application
submit_app() {
    if [ -z "$1" ]; then
        echo "Error: Please provide the path to the Spark application"
        echo "Usage: $0 submit /path/to/app.py"
        exit 1
    fi
    
    echo "Submitting Spark application: $1"
    docker exec -it $SPARK_CLIENT /opt/spark/bin/spark-submit \
        --master $SPARK_MASTER \
        --driver-class-path $(echo '/opt/spark/vast/*.jar' | tr ' ' ':') \
        --conf spark.executor.extraClassPath=$(echo '/opt/spark/vast/*.jar' | tr ' ' ':') \
        --jars $(echo '/opt/spark/vast/*.jar' | tr ' ' ',') \
        "$1"
}

# Function to show cluster status
show_status() {
    echo "=== Spark Cluster Status ==="
    echo ""
    echo "Master Status:"
    docker exec $SPARK_CLIENT curl -s http://spark-master:8080/json/ | python3 -m json.tool 2>/dev/null || echo "Master not accessible"
    echo ""
    echo "Worker Status:"
    docker exec $SPARK_CLIENT curl -s http://spark-worker:8081/json/ | python3 -m json.tool 2>/dev/null || echo "Worker not accessible"
    echo ""
    echo "Container Status:"
    docker ps --filter "name=spark-" --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"
}

# Function to show logs
show_logs() {
    echo "=== Recent Spark Logs ==="
    echo ""
    echo "Master logs:"
    docker logs --tail 20 spark-master
    echo ""
    echo "Worker logs:"
    docker logs --tail 20 spark-worker
    echo ""
    echo "Client logs:"
    docker logs --tail 20 spark-client
}

# Main script logic
case "$1" in
    sql)
        start_sql
        ;;
    pyspark)
        start_pyspark
        ;;
    submit)
        submit_app "$2"
        ;;
    status)
        show_status
        ;;
    logs)
        show_logs
        ;;
    help|--help|-h)
        usage
        ;;
    *)
        echo "Error: Unknown command '$1'"
        echo ""
        usage
        exit 1
        ;;
esac
