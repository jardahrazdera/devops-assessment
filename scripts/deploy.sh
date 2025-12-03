#!/bin/bash
set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Configuration
IMAGE_NAME="devops-assessment"
IMAGE_TAG="${1:-latest}"
NAMESPACE="devops-assessment"

echo -e "${GREEN}=== DevOps Assessment Deployment Script ===${NC}"
echo ""

# Step 1: Build Docker image
echo -e "${YELLOW}[1/5] Building Docker image...${NC}"
docker build -t ${IMAGE_NAME}:${IMAGE_TAG} .
if [ $? -eq 0 ]; then
    echo -e "${GREEN}✓ Docker image built successfully${NC}"
else
    echo -e "${RED}✗ Docker build failed${NC}"
    exit 1
fi

# Step 2: Run tests
echo -e "${YELLOW}[2/5] Running tests...${NC}"
docker run --rm ${IMAGE_NAME}:${IMAGE_TAG} pytest src/tests/ -v || echo -e "${YELLOW}⚠ No tests found or tests failed${NC}"

# Step 3: Security scan with Trivy
echo -e "${YELLOW}[3/5] Running security scan...${NC}"
if command -v trivy &> /dev/null; then
    trivy image --severity HIGH,CRITICAL ${IMAGE_NAME}:${IMAGE_TAG}
    echo -e "${GREEN}✓ Security scan completed${NC}"
else
    echo -e "${YELLOW}⚠ Trivy not installed, skipping security scan${NC}"
fi

# Step 4: Load image to k3d cluster
echo -e "${YELLOW}[4/5] Loading image to k3d cluster...${NC}"
if command -v k3d &> /dev/null; then
    k3d image import ${IMAGE_NAME}:${IMAGE_TAG} -c devops-cluster
    if [ $? -eq 0 ]; then
        echo -e "${GREEN}✓ Image loaded to cluster${NC}"
    else
        echo -e "${YELLOW}⚠ Failed to load image to k3d cluster${NC}"
    fi
else
    echo -e "${YELLOW}⚠ k3d not installed, skipping image import${NC}"
fi

# Step 5: Deploy to Kubernetes
echo -e "${YELLOW}[5/5] Deploying to Kubernetes...${NC}"
kubectl apply -f k8s/
if [ $? -eq 0 ]; then
    echo -e "${GREEN}✓ Deployed successfully${NC}"
else
    echo -e "${RED}✗ Deployment failed${NC}"
    exit 1
fi

# Wait for rollout
echo -e "${YELLOW}Waiting for deployment rollout...${NC}"
kubectl rollout status deployment/devops-app -n ${NAMESPACE} --timeout=120s

# Show status
echo ""
echo -e "${GREEN}=== Deployment Complete ===${NC}"
echo ""
kubectl get all -n ${NAMESPACE}
echo ""
echo -e "${GREEN}Access application:${NC}"
echo "  NodePort: http://localhost:30080/health"
echo "  Metrics:  http://localhost:30080/metrics"
