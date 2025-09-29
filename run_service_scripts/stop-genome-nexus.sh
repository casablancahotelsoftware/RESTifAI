#!/bin/bash
cd "$(dirname "$0")/.."
DEFAULT_DIR="$(pwd)"

TOOL_NAME="${1:-unknown}"

SESSION="genome-nexus"
SERVICE_DIR="services/genome-nexus"

cd $SERVICE_DIR

echo "Stopping Genome Nexus services..."

tmux kill-session -t $SESSION
sleep 5

if docker ps -q -f name=gn-mongo | grep -q .; then
    echo "Stopping MongoDB container..."
    docker stop gn-mongo
fi

echo "Generating JaCoCo HTML report..."

cp -r target/jacoco.exec web/target/jacoco.exec
cd web
mvn jacoco:report
cd ..

TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
REPORT_DIR="$DEFAULT_DIR/results/$SESSION/$TOOL_NAME/jacoco/$TIMESTAMP"
mkdir -p "$REPORT_DIR"
mv web/target/site/jacoco "$REPORT_DIR"

cd "$DEFAULT_DIR"