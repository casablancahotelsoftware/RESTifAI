#!/bin/bash
cd "$(dirname "$0")/.."

SESSION="genome-nexus"
SERVICE_DIR="services/genome-nexus"
SERVICE_PORT="9000"

cd $SERVICE_DIR

if ! docker ps -q -f name=gn-mongo | grep -q .; then
    echo "Starting MongoDB container with pre-imported data..."
    docker stop gn-mongo
    docker rm gn-mongo
    docker run --name=gn-mongo --restart=always -p 27017:27017 -d genomenexus/gn-mongo:latest
    sleep 5
    while ! docker exec gn-mongo mongo --eval "db.adminCommand('ismaster')" >/dev/null 2>&1; do
        echo "Waiting for MongoDB to start..."
        sleep 5
    done
    echo "MongoDB is ready!"
else
    echo "MongoDB container is already running"
fi

mkdir -p target

if [ -f "target/jacoco.exec" ]; then
    rm target/jacoco.exec
fi

if tmux has-session -t $SESSION 2>/dev/null; then
    tmux kill-session -t $SESSION
    sleep 5
fi

JACOCO_AGENT="$HOME/.m2/repository/org/jacoco/org.jacoco.agent/0.8.7/org.jacoco.agent-0.8.7-runtime.jar"
JACOCO_OPTS="-javaagent:$JACOCO_AGENT=destfile=target/jacoco.exec,append=true,includes=org.cbioportal.*"

JAR_FILE=$(find web/target -name "web-*.war" | head -n 1)

echo "Starting Genome Nexus at http://localhost:$SERVICE_PORT"

tmux new-session -d -s $SESSION "java $JACOCO_OPTS -jar $JAR_FILE --server.port=$SERVICE_PORT"

echo "Use 'tmux attach -t $SESSION' to view logs."
echo "Waiting 60 seconds for Genome Nexus to start..."

sleep 60