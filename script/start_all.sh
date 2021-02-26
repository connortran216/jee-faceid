#!/usr/bin/env bash
docker-compose \
    -f docker-compose.gpu.yml \
    -f docker-compose.stream.yml \
    -f docker-compose.database.yml \
    -f docker-compose.admin.yml up -d \
#     --scale detector=3 \
#     --scale embedder=3 \
#     --scale register-response-handler=2 \
#     --scale verifier-response-handler=2 \
