#!/bin/bash

# Copy the streaming scripts to the spark-client container
docker compose cp services/pyspark/scripts/streaming_consumer_fluentd_topic.py spark-client:/opt/spark/

# Execute the scripts inside the container
docker compose exec -it spark-client bash -c "pip3 install --quiet vastdb"

# Get the classpaths and jars
driver_class_path=$(docker compose exec -it spark-client bash -c "find /opt/spark/vast -name '*.jar' | tr '\n' ':'")
executor_extra_classpath=$(docker compose exec -it spark-client bash -c "find /opt/spark/vast -name '*.jar' | tr '\n' ':'")
jars=$(docker compose exec -it spark-client bash -c "find /opt/spark/vast -name '*.jar' | tr '\n' ','")

echo "------"
echo "Driver class path: $driver_class_path"
echo "Executor extra classpath: $executor_extra_classpath"
echo "Jars: $jars"
echo "------"

# Execute the scripts inside the container
read -r -d '' SPARK_COMMAND <<EOF
echo "Submitting streaming_consumer_fluentd_topic.py..."
spark-submit --master spark://spark-master:7077 \
  /opt/spark/streaming_consumer_fluentd_topic.py \
  --driver-class-path "$driver_class_path" \
  --conf spark.executor.extraClassPath="$executor_extra_classpath" \
  --jars "$jars" \
  --conf spark.executor.userClassPathFirst=true \
  --conf spark.driver.userClassPathFirst=true \
  --conf spark.driver.maxResultSize=4g \
  --conf spark.driver.memory=16g \
  --conf spark.executor.cores=8 \
  --conf spark.executor.memory=8g \
  --conf spark.sql.catalogImplementation=in-memory \
  --packages org.apache.spark:spark-sql-kafka-0-10_2.13:3.4.3
EOF

docker compose exec -it spark-client bash -cx "$SPARK_COMMAND"

echo "Streaming scripts submitted."
