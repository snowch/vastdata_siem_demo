#!/usr/bin/env bash

# Ensure the script stops if any command fails
set -e

echo
echo

curl -X POST -H "Content-Type: application/json" -d '{}' http://localhost:8080/api/continuous/stop
curl -X GET http://localhost:8080/api/continuous/status

echo
echo

curl -X POST -H "Content-Type: application/json" -d '{"min_interval":1,"max_interval":10,"max_concurrent":20}' http://localhost:8080/api/continuous/start

echo
echo

curl -X GET http://localhost:8080/api/continuous/status
