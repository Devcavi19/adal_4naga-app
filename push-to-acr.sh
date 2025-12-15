#!/bin/bash

# Push Docker image to Azure Container Registry
# Usage: ./push-to-acr.sh [IMAGE_TAG]
# Example: ./push-to-acr.sh 1.0.0
# Example: ./push-to-acr.sh latest

set -e

# Configuration
AZURE_REGISTRY_NAME="adalnagaregistry"
AZURE_REGISTRY_LOGIN_SERVER="adalnagaregistry.azurecr.io"
IMAGE_NAME="adal-4naga-app"
IMAGE_TAG="${1:-latest}"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${YELLOW}================================${NC}"
echo -e "${YELLOW}Azure Container Registry Push${NC}"
echo -e "${YELLOW}================================${NC}"

# Step 1: Verify Azure CLI is installed
echo -e "\n${YELLOW}Checking Azure CLI...${NC}"
if ! command -v az &> /dev/null; then
    echo -e "${RED}ERROR: Azure CLI is not installed.${NC}"
    echo "Install Azure CLI: https://learn.microsoft.com/en-us/cli/azure/install-azure-cli"
    exit 1
fi
echo -e "${GREEN}✓ Azure CLI found${NC}"

# Step 2: Check if user is logged in to Azure
echo -e "\n${YELLOW}Verifying Azure login...${NC}"
if ! az account show > /dev/null 2>&1; then
    echo -e "${YELLOW}Not logged into Azure. Launching login...${NC}"
    az login
else
    echo -e "${GREEN}✓ Already logged into Azure${NC}"
fi

# Step 3: Verify ACR exists and get credentials
echo -e "\n${YELLOW}Verifying ACR access...${NC}"
if ! az acr show --name "$AZURE_REGISTRY_NAME" > /dev/null 2>&1; then
    echo -e "${RED}ERROR: Cannot access registry '$AZURE_REGISTRY_NAME'${NC}"
    exit 1
fi
echo -e "${GREEN}✓ ACR '$AZURE_REGISTRY_NAME' accessible${NC}"

# Step 4: Login to ACR
echo -e "\n${YELLOW}Logging into ACR...${NC}"
az acr login --name "$AZURE_REGISTRY_NAME"
echo -e "${GREEN}✓ Logged into ACR${NC}"

# Step 5: Build the Docker image
echo -e "\n${YELLOW}Building Docker image...${NC}"
echo "Command: docker build -t ${AZURE_REGISTRY_LOGIN_SERVER}/${IMAGE_NAME}:${IMAGE_TAG} ."
docker build -t "${AZURE_REGISTRY_LOGIN_SERVER}/${IMAGE_NAME}:${IMAGE_TAG}" .

# Also tag as latest if not already
if [ "$IMAGE_TAG" != "latest" ]; then
    docker tag "${AZURE_REGISTRY_LOGIN_SERVER}/${IMAGE_NAME}:${IMAGE_TAG}" "${AZURE_REGISTRY_LOGIN_SERVER}/${IMAGE_NAME}:latest"
    echo -e "${GREEN}✓ Tagged as 'latest' as well${NC}"
fi

echo -e "${GREEN}✓ Docker image built successfully${NC}"

# Step 6: Push to ACR
echo -e "\n${YELLOW}Pushing image to ACR...${NC}"
echo "Command: docker push ${AZURE_REGISTRY_LOGIN_SERVER}/${IMAGE_NAME}:${IMAGE_TAG}"
docker push "${AZURE_REGISTRY_LOGIN_SERVER}/${IMAGE_NAME}:${IMAGE_TAG}"

if [ "$IMAGE_TAG" != "latest" ]; then
    docker push "${AZURE_REGISTRY_LOGIN_SERVER}/${IMAGE_NAME}:latest"
fi

echo -e "${GREEN}✓ Image pushed successfully${NC}"

# Step 7: List images in ACR
echo -e "\n${YELLOW}Images in ACR:${NC}"
az acr repository show-tags --name "$AZURE_REGISTRY_NAME" --repository "$IMAGE_NAME"

echo -e "\n${GREEN}================================${NC}"
echo -e "${GREEN}✓ Push completed successfully!${NC}"
echo -e "${GREEN}================================${NC}"
echo -e "\n${YELLOW}Image reference:${NC}"
echo -e "  ${GREEN}${AZURE_REGISTRY_LOGIN_SERVER}/${IMAGE_NAME}:${IMAGE_TAG}${NC}"
echo -e "\n${YELLOW}To deploy to Azure App Service:${NC}"
echo -e "  ${GREEN}az container create --resource-group <rg> --name <app-name> \\${NC}"
echo -e "  ${GREEN}  --image ${AZURE_REGISTRY_LOGIN_SERVER}/${IMAGE_NAME}:${IMAGE_TAG} \\${NC}"
echo -e "  ${GREEN}  --registry-login-server ${AZURE_REGISTRY_LOGIN_SERVER} \\${NC}"
echo -e "  ${GREEN}  --registry-username <username> --registry-password <password>${NC}"
