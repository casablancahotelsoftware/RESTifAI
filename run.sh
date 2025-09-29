#!/bin/bash

# Usage: ./run.sh --tool <tool> --service <service>
# Example: ./run.sh --tool RESTifAI --service genome-nexus

ROOT_DIR=$(pwd)

SCRIPTS_DIR="run_service_scripts"
TOOL=""
SERVICE=""
TIME="100"

# Supported tools
TOOLS=("AutoRestTest" "RESTifAI" "LogiAgent")
# Supported services
SERVICES=("genome-nexus" "fdic" "ohsome" "language-tool" "rest-countries")
ONLINE_SERVICES=("fdic" "ohsome")

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --tool)
            TOOL="$2"
            shift 2
            ;;
        --service)
            SERVICE="$2"
            shift 2
            ;;
        --time)
            TIME="$2"
            shift 2
            ;;
        *)
            echo "Unknown argument: $1"
            exit 1
            ;;
    esac
done

if [[ -z "$TOOL" || -z "$SERVICE" ]]; then
    echo "Usage: $0 --tool <tool> --service <service>"
    echo "Available tools: ${TOOLS[*]}"
    echo "Available services: ${SERVICES[*]}"
    exit 1
fi

# Validate tool
if [[ ! " ${TOOLS[@]} " =~ " $TOOL " ]]; then
    echo "Invalid tool: $TOOL"
    echo "Available tools: ${TOOLS[*]}"
    exit 2
fi

# Validate service
if [[ ! " ${SERVICES[@]} " =~ " $SERVICE " ]]; then
    echo "Invalid service: $SERVICE"
    echo "Available services: ${SERVICES[*]}"
    exit 2
fi

URL=""

if [[ "$SERVICE" == "genome-nexus" ]]; then
    URL="http://localhost:9000/"
elif [[ "$SERVICE" == "language-tool" ]]; then
    URL="http://localhost:9001/v2"
elif [[ "$SERVICE" == "rest-countries" ]]; then
    URL="http://localhost:9002/rest"
elif [[ "$SERVICE" == "fdic" ]]; then
    URL="https://banks.data.fdic.gov/api"
elif [[ "$SERVICE" == "ohsome" ]]; then
    URL="https://api.ohsome.org/v1"
fi

START_SCRIPT=""
STOP_SCRIPT=""

if [[ ! " ${ONLINE_SERVICES[@]} " =~ " $SERVICE " ]]; then
    START_SCRIPT="$SCRIPTS_DIR/start-$SERVICE.sh"
    STOP_SCRIPT="$SCRIPTS_DIR/stop-$SERVICE.sh"
fi

# Start the service
if [[ -x "$START_SCRIPT" ]]; then
    "$START_SCRIPT"
fi

cd "$ROOT_DIR"

REPORT_DIR="$ROOT_DIR/results/$SERVICE/$TOOL"
mkdir -p "$REPORT_DIR"

case $TOOL in
    AutoRestTest)
        cd tools/AutoRestTest
        echo "Starting AutoRestTest"

        docker run -it --network="host" -v "$REPORT_DIR":/app/data autoresttest -s $SERVICE --time $TIME
        ;;
    RESTifAI)
        cd tools/RESTifAI
        echo "Starting RESTifAI"

        docker run -it --network="host" -v "$REPORT_DIR":/app/output restifai -s specifications/$SERVICE.json -u $URL
        ;;
    LogiAgent)
        echo "Starting LogiAgent"
        
        docker run -it --network="host" -v "$REPORT_DIR":/app/logs logiagent python3 logi_agent.py --system-name "$SERVICE" --base-url "$URL" --max-time $TIME
        ;;
    *)
        echo "Unknown tool: $TOOL"
        ;;
esac

cd "$ROOT_DIR"

# Stop the service
if [[ -x "$STOP_SCRIPT" ]]; then
    "$STOP_SCRIPT" "$TOOL" 
fi