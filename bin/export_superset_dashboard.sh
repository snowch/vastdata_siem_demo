#!/usr/bin/env bash

# Ensure the script stops if any command fails
set -e

# Change to the script's directory
script_dir="$(dirname "$0")"

# Export the Superset dashboard
docker exec -it superset_app superset export-dashboards -f /tmp/superset_dashboards_export.zip

# Copy the exported dashboard to the host machine
docker cp superset_app:/tmp/superset_dashboards_export.zip ${script_dir}/../services/superset/siem_dashboard_export.zip

echo "Dashboard exported to: ${script_dir}/../services/superset/superset_dashboards_export.zip"
