#!/usr/bin/env bash
docker-compose \
    -f docker-compose.yml \
    -f docker-compose.stream.yml \
    -f docker-compose.database.yml down
