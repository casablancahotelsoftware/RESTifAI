#!/bin/bash
cd "$(dirname "$0")/.."
DEFAULT_DIR="$(pwd)"

TOOL_NAME="${1:-unknown}"

SESSION="rest-countries"
SERVICE_DIR="services/restcountries"

cd $SERVICE_DIR

tmux kill-session -t $SESSION
sleep 5

mvn jacoco:report

TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
REPORT_DIR="$DEFAULT_DIR/results/$SESSION/$TOOL_NAME/jacoco/$TIMESTAMP"
mkdir -p "$REPORT_DIR"
mv target/site/jacoco "$REPORT_DIR"

cd "$DEFAULT_DIR"