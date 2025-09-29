#!/bin/bash

DEFAULT_DIR=$(pwd)

# Update system packages
sudo apt-get update

# Install essential packages
sudo apt-get install -y curl wget git unzip dos2unix

# Install Python and pip for evaluation
echo "Installing Python..."
sudo apt-get install -y python3 python3-pip python3-venv

# Install Java
sudo apt update
sudo apt-get install -y openjdk-8-jdk
sudo apt-get install -y openjdk-11-jdk
sudo apt-get install -y openjdk-17-jdk

# Install Maven (required for building Genome Nexus)
echo "Installing Maven..."
sudo apt-get install -y maven

# Download JaCoCo for Java 17 support
echo "Installing JaCoCo 0.8.7 for Java 17 support..."
mvn dependency:get -Dartifact=org.jacoco:org.jacoco.agent:0.8.7:jar:runtime
mvn dependency:get -Dartifact=org.jacoco:org.jacoco.cli:0.8.7:jar:nodeps

# Add Docker's official GPG key:
sudo install -m 0755 -d /etc/apt/keyrings
sudo curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
sudo chmod a+r /etc/apt/keyrings/docker.asc

# Add the repository to Apt sources:
echo \
  "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/ubuntu \
  $(. /etc/os-release && echo "${UBUNTU_CODENAME:-$VERSION_CODENAME}") stable" | \
  sudo tee /etc/apt/sources.list.d/docker.list > /dev/null
sudo apt-get update

# Install Docker
echo "Installing Docker..."
sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-compose-plugin

# Start Docker service
sudo systemctl start docker
sudo systemctl enable docker

# Verify Java installation
echo "Verifying Java installation..."
java -version
javac -version

# Verify Maven installation
echo "Verifying Maven installation..."
mvn -version

# Verify Docker installation
echo "Verifying Docker installation..."
docker --version

# Build Genome-Nexus
echo "Setting up Genome Nexus..."
cd $DEFAULT_DIR
cd services/genome-nexus
docker pull genomenexus/gn-mongo:latest
mvn clean package -DskipTests

# Build REST Countries
echo "Setting up REST Countries service..."
cd $DEFAULT_DIR
cd services/restcountries
mvn clean package -DskipTests

# Build RESTifAI
cd $DEFAULT_DIR
cd tools/RESTifAI && docker build -t restifai .

# Build AutoRestTest
cd $DEFAULT_DIR
cd tools/AutoRestTest && docker build -t autoresttest .

# Build LogiAgent
cd $DEFAULT_DIR
cd tools/LogiAgent && docker build -t logiagent .

cd $DEFAULT_DIR
