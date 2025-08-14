#!/usr/bin/env bash

# Change to the script's directory
cd "$(dirname "$0")"

DOCKER_CMD="docker compose -f ../../docker-compose.yml"

$DOCKER_CMD build bytewax-fluentd-etl && \
    $DOCKER_CMD down bytewax-fluentd-etl && \
    $DOCKER_CMD up -d bytewax-fluentd-etl

$DOCKER_CMD down bytewax-zeek-etl && \
$DOCKER_CMD up -d bytewax-zeek-etl