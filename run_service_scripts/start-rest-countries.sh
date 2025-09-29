#!/bin/bash
cd "$(dirname "$0")/.."

SESSION="rest-countries"
SERVICE_DIR="services/restcountries"
SERVICE_PORT="9002"

echo "Starting REST Countries service at http://localhost:$SERVICE_PORT"

if tmux has-session -t $SESSION 2>/dev/null; then
    tmux kill-session -t $SESSION
    sleep 5
fi

cd $SERVICE_DIR

JAR_FILE="target/restcountries-sut.jar"
JACOCO_AGENT="$HOME/.m2/repository/org/jacoco/org.jacoco.agent/0.8.7/org.jacoco.agent-0.8.7-runtime.jar"
JACOCO_OPTS="-javaagent:$JACOCO_AGENT=destfile=target/jacoco.exec,append=true,includes=eu.fayder.restcountries.*,dumponexit=true"

mkdir -p target
if [ -f "target/jacoco.exec" ]; then
    rm target/jacoco.exec
fi

echo "Starting REST Countries service on port $SERVICE_PORT..."

tmux new-session -d -s $SESSION "java $JACOCO_OPTS -jar $JAR_FILE --server.port=$SERVICE_PORT"

echo "Use 'tmux attach -t $SESSION' to view logs."
echo "Waiting 10 seconds for service to start..."
sleep 10
