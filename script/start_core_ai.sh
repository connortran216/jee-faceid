#!/usr/bin/env bash
docker-compose \
    -f docker-compose.yml \
    -f docker-compose.stream.yml \
    -f docker-compose.database.yml up -d \
    --scale detector=2 \
    --scale embedder=2 \
    --scale register-response-handler=2 \
    --scale recognizer-response-handler=2 \
    --scale verifier-response-handler=2 \
    --scale updater=2
