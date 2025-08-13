#!/usr/bin/env bash

# Change to the script's directory
cd "$(dirname "$0")"

DOCKER_CMD="docker compose -f ../../docker-compose.yml"

$DOCKER_CMD logs -f ai-agents