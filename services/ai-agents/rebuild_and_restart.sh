#!/usr/bin/env bash

# Change to the script's directory
cd "$(dirname "$0")"

DOCKER_CMD="docker compose -f ../../docker-compose.yml"

$DOCKER_CMD build ai-agents --no-cache && \
    $DOCKER_CMD down ai-agents && \
    $DOCKER_CMD up -d ai-agents
