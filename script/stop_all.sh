#!/usr/bin/env bash
docker-compose \
    -f docker-compose.gpu.yml \
    -f docker-compose.stream.yml \
    -f docker-compose.database.yml \
    -f docker-compose.admin.yml down \
    --remove-orphans
