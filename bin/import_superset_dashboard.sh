#!/usr/bin/env bash

# Ensure the script stops if any command fails
set -e

# Change to the script's directory
script_dir="$(dirname "$0")"

docker cp ${script_dir}/../services/superset/siem_dashboard.zip superset_app:/tmp/

docker exec -it superset_app superset import-dashboards --path /tmp/siem_dashboard.zip -u admin 2>&1



