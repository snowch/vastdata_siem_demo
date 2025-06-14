#!/usr/bin/env bash

# Ensure the script stops if any command fails
set -e

# Change to the script's directory
script_dir="$(dirname "$0")"

docker exec -it superset_app rm -f /tmp/siem_dashboard.zip

# Export the Superset dashboard
docker exec -it superset_app superset export-dashboards -f /tmp/siem_dashboard.zip

sudo rm ${script_dir}/../services/superset/siem_dashboard.zip

# Copy the exported dashboard to the host machine
docker cp superset_app:/tmp/siem_dashboard.zip ${script_dir}/../services/superset/siem_dashboard.zip

echo "Dashboard exported to: ${script_dir}/../services/superset/siem_dashboard.zip"
