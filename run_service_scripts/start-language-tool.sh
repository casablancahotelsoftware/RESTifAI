#!/bin/bash
cd "$(dirname "$0")/.."

SESSION="language-tool"
SERVICE_DIR="services/LanguageTool-6.7-SNAPSHOT"
SERVICE_PORT="9001"

cd $SERVICE_DIR

if [ -f "target/jacoco.exec" ]; then
    rm target/jacoco.exec
fi

JAR_FILE="./languagetool-server.jar"
JAVA_17="/usr/lib/jvm/java-17-openjdk-amd64/bin/java"

if tmux has-session -t $SESSION 2>/dev/null; then
    tmux kill-session -t $SESSION
    sleep 5
fi

mkdir -p target/site/jacoco

JACOCO_AGENT="$HOME/.m2/repository/org/jacoco/org.jacoco.agent/0.8.7/org.jacoco.agent-0.8.7-runtime.jar"
JACOCO_OPTS="-javaagent:$JACOCO_AGENT=destfile=target/jacoco.exec,append=true,includes=org.languagetool.*"

echo "Starting LanguageTool with JaCoCo at http://localhost:$SERVICE_PORT/v2/"

tmux new-session -d -s $SESSION "export JAVA_OPTS='$JACOCO_OPTS' && '$JAVA_17' \$JAVA_OPTS -jar '$JAR_FILE' --port $SERVICE_PORT"

echo "Use 'tmux attach -t $SESSION' to view logs."
echo "Waiting 10 seconds for LanguageTool to start..."
sleep 10