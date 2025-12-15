#!/bin/bash

# Local Docker build and test script
# Usage: ./build-and-test.sh [TAG]
# Example: ./build-and-test.sh latest
# Example: ./build-and-test.sh 1.0.0

set -e

IMAGE_TAG="${1:-latest}"
IMAGE_NAME="adal-4naga-app:${IMAGE_TAG}"
CONTAINER_NAME="adal-4naga-test"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${YELLOW}================================${NC}"
echo -e "${YELLOW}Docker Build & Local Test${NC}"
echo -e "${YELLOW}================================${NC}"

# Step 1: Check if container is already running
echo -e "\n${YELLOW}Checking for existing containers...${NC}"
if docker ps -a --format '{{.Names}}' | grep -q "^${CONTAINER_NAME}$"; then
    echo -e "${YELLOW}Removing existing container: ${CONTAINER_NAME}${NC}"
    docker stop "${CONTAINER_NAME}" 2>/dev/null || true
    docker rm "${CONTAINER_NAME}" 2>/dev/null || true
fi

# Step 2: Build the Docker image
echo -e "\n${YELLOW}Building Docker image: ${IMAGE_NAME}${NC}"
docker build -t "${IMAGE_NAME}" .

if [ $? -ne 0 ]; then
    echo -e "${RED}✗ Docker build failed!${NC}"
    exit 1
fi
echo -e "${GREEN}✓ Docker image built successfully${NC}"

# Step 3: Get image info
echo -e "\n${YELLOW}Image Information:${NC}"
docker images --format "table {{.Repository}}\t{{.Tag}}\t{{.Size}}" | grep "${IMAGE_NAME}" || true

# Step 4: Start container
echo -e "\n${YELLOW}Starting container for testing...${NC}"
docker run -d \
  --name "${CONTAINER_NAME}" \
  -p 8080:8080 \
  -e FLASK_ENV=production \
  "${IMAGE_NAME}"

if [ $? -ne 0 ]; then
    echo -e "${RED}✗ Container failed to start!${NC}"
    exit 1
fi

echo -e "${GREEN}✓ Container started successfully${NC}"
echo -e "${YELLOW}Container ID: ${NC}$(docker ps --format '{{.ID}}' -f name="${CONTAINER_NAME}")"

# Step 5: Wait for application to start
echo -e "\n${YELLOW}Waiting for application to start (up to 30 seconds)...${NC}"
max_attempts=30
attempt=0

while [ $attempt -lt $max_attempts ]; do
    if curl -sf http://localhost:8080/health > /dev/null 2>&1; then
        echo -e "${GREEN}✓ Application is ready!${NC}"
        break
    fi
    
    attempt=$((attempt + 1))
    if [ $attempt -lt $max_attempts ]; then
        echo -e "${YELLOW}  Waiting... (${attempt}/${max_attempts})${NC}"
        sleep 1
    fi
done

if [ $attempt -eq $max_attempts ]; then
    echo -e "${RED}✗ Application failed to start within timeout${NC}"
    echo -e "\n${YELLOW}Container logs:${NC}"
    docker logs "${CONTAINER_NAME}"
    docker stop "${CONTAINER_NAME}"
    docker rm "${CONTAINER_NAME}"
    exit 1
fi

# Step 6: Test endpoints
echo -e "\n${YELLOW}Testing endpoints...${NC}"

# Health check
echo -ne "${YELLOW}  Health endpoint... ${NC}"
if curl -sf http://localhost:8080/health > /dev/null; then
    echo -e "${GREEN}✓${NC}"
else
    echo -e "${RED}✗${NC}"
fi

# Root endpoint
echo -ne "${YELLOW}  Root endpoint... ${NC}"
if curl -sf http://localhost:8080/ > /dev/null; then
    echo -e "${GREEN}✓${NC}"
else
    echo -e "${RED}✗${NC}"
fi

# Step 7: Show container stats
echo -e "\n${YELLOW}Container Statistics:${NC}"
docker stats --no-stream "${CONTAINER_NAME}" --format "table {{.Container}}\t{{.CPUPerc}}\t{{.MemUsage}}"

# Step 8: Show logs
echo -e "\n${YELLOW}Container Logs (last 10 lines):${NC}"
docker logs --tail 10 "${CONTAINER_NAME}"

# Step 9: Cleanup or keep running
echo -e "\n${GREEN}================================${NC}"
echo -e "${GREEN}✓ Build and test completed!${NC}"
echo -e "${GREEN}================================${NC}"

echo -e "\n${YELLOW}Container Status:${NC}"
docker ps --filter "name=${CONTAINER_NAME}" --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"

echo -e "\n${YELLOW}Next Steps:${NC}"
echo -e "  ${GREEN}View logs:${NC}         docker logs -f ${CONTAINER_NAME}"
echo -e "  ${GREEN}Stop container:${NC}    docker stop ${CONTAINER_NAME}"
echo -e "  ${GREEN}Remove container:${NC}  docker rm ${CONTAINER_NAME}"
echo -e "  ${GREEN}Push to ACR:${NC}       ./push-to-acr.sh ${IMAGE_TAG}"

echo -e "\n${YELLOW}Test the application:${NC}"
echo -e "  ${GREEN}Health:${NC}  curl http://localhost:8080/health"
echo -e "  ${GREEN}Home:${NC}    curl http://localhost:8080/"
