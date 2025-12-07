#!/bin/bash
set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Parse arguments
IMAGE_TAG="latest"
INSTALL_ARGOCD=false

for arg in "$@"; do
  case $arg in
    --argocd)
      INSTALL_ARGOCD=true
      shift
      ;;
    *)
      IMAGE_TAG="$arg"
      shift
      ;;
  esac
done

# Configuration
IMAGE_NAME="devops-assessment"
NAMESPACE="devops-assessment"
CLUSTER_NAME="devops-cluster"

echo -e "${GREEN}=== DevOps Assessment Deployment Script ===${NC}"
echo -e "${BLUE}Image: ${IMAGE_NAME}:${IMAGE_TAG}${NC}"
if [ "$INSTALL_ARGOCD" = true ]; then
    echo -e "${BLUE}ArgoCD: Enabled${NC}"
fi
echo ""

# Step 0: Check/Create k3d cluster
echo -e "${YELLOW}[0/6] Checking k3d cluster...${NC}"
if command -v k3d &> /dev/null; then
    if ! k3d cluster list | grep -q "^${CLUSTER_NAME}"; then
        echo -e "${BLUE}Creating k3d cluster with NodePort mappings...${NC}"
        k3d cluster create ${CLUSTER_NAME} \
            -p "30080:30080@loadbalancer" \
            -p "30090:30090@loadbalancer" \
            -p "30030:30030@loadbalancer" \
            -p "30081:30081@loadbalancer" \
            --wait
        echo -e "${GREEN}✓ k3d cluster created${NC}"
    else
        CLUSTER_STATUS=$(k3d cluster list | grep "^${CLUSTER_NAME}" | awk '{print $3}')
        if [ "$CLUSTER_STATUS" != "1/1" ]; then
            echo -e "${BLUE}Starting k3d cluster...${NC}"
            k3d cluster start ${CLUSTER_NAME}
            sleep 5
        fi
        echo -e "${GREEN}✓ k3d cluster ready${NC}"
    fi
else
    echo -e "${YELLOW}⚠ k3d not installed, assuming cluster exists${NC}"
fi

# Step 1: Build Docker image
echo -e "${YELLOW}[1/6] Building Docker image...${NC}"
docker build -t ${IMAGE_NAME}:${IMAGE_TAG} .
if [ $? -eq 0 ]; then
    echo -e "${GREEN}✓ Docker image built successfully${NC}"
else
    echo -e "${RED}✗ Docker build failed${NC}"
    exit 1
fi

# Step 2: Run tests
echo -e "${YELLOW}[2/6] Running tests...${NC}"
if docker run --rm ${IMAGE_NAME}:${IMAGE_TAG} pytest src/tests/ -v; then
    echo -e "${GREEN}✓ All tests passed${NC}"
else
    echo -e "${RED}✗ Tests failed${NC}"
    exit 1
fi

# Step 3: Security scan with Trivy
echo -e "${YELLOW}[3/6] Running security scan...${NC}"
if command -v trivy &> /dev/null; then
    trivy image --severity HIGH,CRITICAL ${IMAGE_NAME}:${IMAGE_TAG} --exit-code 0
    echo -e "${GREEN}✓ Security scan completed${NC}"
else
    echo -e "${YELLOW}⚠ Trivy not installed, skipping security scan${NC}"
fi

# Step 4: Load image to k3d cluster
echo -e "${YELLOW}[4/6] Loading image to k3d cluster...${NC}"
if command -v k3d &> /dev/null; then
    k3d image import ${IMAGE_NAME}:${IMAGE_TAG} -c ${CLUSTER_NAME}
    if [ $? -eq 0 ]; then
        echo -e "${GREEN}✓ Image loaded to cluster${NC}"
    else
        echo -e "${RED}✗ Failed to load image to k3d cluster${NC}"
        exit 1
    fi
else
    echo -e "${YELLOW}⚠ k3d not installed, skipping image import${NC}"
fi

# Step 5: Deploy to Kubernetes
echo -e "${YELLOW}[5/6] Deploying to Kubernetes...${NC}"

# Apply namespace first
echo -e "${BLUE}  - Creating namespace...${NC}"
kubectl apply -f k8s/namespace.yaml
sleep 2

# Generate secrets from templates if they don't exist
echo -e "${BLUE}  - Generating secrets from templates...${NC}"

# Set default credentials (override with environment variables)
export POSTGRES_USER="${POSTGRES_USER:-devops}"
export POSTGRES_PASSWORD="${POSTGRES_PASSWORD:-devops123}"
export POSTGRES_DB="${POSTGRES_DB:-devopsdb}"

# Generate secrets from templates using envsubst
if command -v envsubst &> /dev/null; then
    envsubst < k8s/postgres-secret.yaml.template > k8s/postgres-secret.yaml
    envsubst < k8s/app-secret.yaml.template > k8s/app-secret.yaml
    echo -e "${GREEN}✓ Secrets generated from templates${NC}"
else
    echo -e "${RED}✗ envsubst not found. Install gettext package${NC}"
    echo -e "${YELLOW}  Ubuntu/Debian: sudo apt-get install gettext-base${NC}"
    echo -e "${YELLOW}  macOS: brew install gettext${NC}"
    exit 1
fi

# Apply secrets
echo -e "${BLUE}  - Applying Secrets...${NC}"
kubectl apply -f k8s/postgres-secret.yaml
kubectl apply -f k8s/app-secret.yaml

# Apply remaining resources
echo -e "${BLUE}  - Applying ConfigMap...${NC}"
kubectl apply -f k8s/configmap.yaml

echo -e "${BLUE}  - Deploying PostgreSQL...${NC}"
kubectl apply -f k8s/postgres-service.yaml
kubectl apply -f k8s/postgres-deployment.yaml

echo -e "${BLUE}  - Waiting for PostgreSQL to be ready...${NC}"
kubectl wait --for=condition=ready pod -l app=postgres -n ${NAMESPACE} --timeout=120s

echo -e "${BLUE}  - Applying Service...${NC}"
kubectl apply -f k8s/service.yaml

echo -e "${BLUE}  - Applying Deployment...${NC}"
kubectl apply -f k8s/deployment.yaml

echo -e "${GREEN}✓ Application resources deployed${NC}"

# Deploy monitoring stack
echo -e "${BLUE}  - Deploying monitoring namespace...${NC}"
kubectl apply -f k8s/monitoring/namespace.yaml
sleep 2

echo -e "${BLUE}  - Deploying Prometheus and Grafana...${NC}"
kubectl apply -f k8s/monitoring/prometheus-configmap.yaml
kubectl apply -f k8s/monitoring/prometheus-deployment.yaml
kubectl apply -f k8s/monitoring/prometheus-service.yaml
kubectl apply -f k8s/monitoring/grafana-configmap.yaml
kubectl apply -f k8s/monitoring/grafana-dashboard-provider.yaml
kubectl apply -f k8s/monitoring/grafana-dashboard.yaml
kubectl apply -f k8s/monitoring/grafana-deployment.yaml
kubectl apply -f k8s/monitoring/grafana-service.yaml

echo -e "${GREEN}✓ All resources deployed${NC}"

# Optional: Install ArgoCD
if [ "$INSTALL_ARGOCD" = true ]; then
    echo ""
    echo -e "${YELLOW}Installing ArgoCD...${NC}"

    # Create ArgoCD namespace and install
    echo -e "${BLUE}  - Creating argocd namespace...${NC}"
    kubectl create namespace argocd --dry-run=client -o yaml | kubectl apply -f -

    echo -e "${BLUE}  - Installing ArgoCD manifests...${NC}"
    kubectl apply -n argocd -f https://raw.githubusercontent.com/argoproj/argo-cd/stable/manifests/install.yaml

    echo -e "${BLUE}  - Waiting for ArgoCD to be ready...${NC}"
    kubectl wait --for=condition=available --timeout=300s deployment/argocd-server -n argocd

    # Patch ArgoCD server to use NodePort
    echo -e "${BLUE}  - Exposing ArgoCD server on NodePort 30081...${NC}"
    kubectl patch svc argocd-server -n argocd -p '{"spec":{"type":"NodePort","ports":[{"port":443,"targetPort":8080,"nodePort":30081}]}}'

    # Deploy ArgoCD Application
    echo -e "${BLUE}  - Deploying ArgoCD application...${NC}"
    kubectl apply -f argocd/application.yaml

    echo -e "${GREEN}✓ ArgoCD installed and configured${NC}"
fi

# Step 6: Wait for rollout
echo -e "${YELLOW}[6/6] Waiting for deployment rollout...${NC}"
if kubectl rollout status deployment/devops-app -n ${NAMESPACE} --timeout=120s; then
    echo -e "${GREEN}✓ Deployment rolled out successfully${NC}"
else
    echo -e "${RED}✗ Deployment rollout failed${NC}"
    echo -e "${YELLOW}Checking pod status:${NC}"
    kubectl get pods -n ${NAMESPACE}
    echo -e "${YELLOW}Pod logs:${NC}"
    kubectl logs -n ${NAMESPACE} -l app=devops-app --tail=20
    exit 1
fi

# Show status
echo ""
echo -e "${GREEN}=== Deployment Complete ===${NC}"
echo ""
kubectl get all -n ${NAMESPACE}
echo ""
echo -e "${GREEN}Access application:${NC}"
echo "  Application:  http://localhost:30080/health"
echo "  API Docs:     http://localhost:30080/docs"
echo "  Metrics:      http://localhost:30080/metrics"
echo ""
echo -e "${GREEN}Access monitoring:${NC}"
echo "  Prometheus:   http://localhost:30090"
echo "  Grafana:      http://localhost:30030 (admin/admin)"
echo ""
if [ "$INSTALL_ARGOCD" = true ]; then
    echo -e "${GREEN}Access ArgoCD:${NC}"
    echo "  ArgoCD UI:    http://localhost:30081"
    echo "  Username:     admin"
    echo "  Password:     kubectl -n argocd get secret argocd-initial-admin-secret -o jsonpath='{.data.password}' | base64 -d"
    echo ""
fi
echo -e "${GREEN}Useful commands:${NC}"
echo "  App logs:    kubectl logs -n ${NAMESPACE} -l app=devops-app -f"
echo "  All pods:    kubectl get pods -A"
echo "  Port-forward: kubectl port-forward -n ${NAMESPACE} svc/devops-app-service 8080:80"
