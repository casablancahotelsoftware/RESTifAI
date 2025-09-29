#!/bin/bash

# Simple FastAPI Container Reset Script
# Stops all FastAPI containers and restarts them using docker compose (simple but not the fastest way)

set -e

ROOT_DIR=$(pwd)

FASTAPI_PROJECT_PATH="/root/projekts/full-stack-fastapi-template"

cd "$FASTAPI_PROJECT_PATH"
docker compose down -v
docker compose up -d

sleep 2  # Wait for a few seconds to ensure the containers are up and running

cd "$ROOT_DIR"