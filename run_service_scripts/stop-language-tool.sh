#!/bin/bash
cd "$(dirname "$0")/.."
DEFAULT_DIR="$(pwd)"

TOOL_NAME="${1:-unknown}"

SESSION="language-tool"
SERVICE_DIR="services/LanguageTool-6.7-SNAPSHOT"

cd $SERVICE_DIR

tmux kill-session -t $SESSION
sleep 5

JACOCO_CLI="$HOME/.m2/repository/org/jacoco/org.jacoco.cli/0.8.7/org.jacoco.cli-0.8.7-nodeps.jar"

TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
REPORT_DIR="$DEFAULT_DIR/results/$SESSION/$TOOL_NAME/jacoco/$TIMESTAMP"
cd "$DEFAULT_DIR" && mkdir -p "$REPORT_DIR" && cd $SERVICE_DIR
    
JAR_FILE="./languagetool-server.jar"
    
java -jar "$JACOCO_CLI" report target/jacoco.exec \
    --classfiles "$JAR_FILE" \
    --html "$REPORT_DIR" \
    --name "LanguageTool Coverage Report - $TOOL_NAME"

cd "$DEFAULT_DIR"