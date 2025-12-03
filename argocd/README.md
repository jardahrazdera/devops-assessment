# ArgoCD Setup Guide

## Install ArgoCD

```bash
# Create namespace
kubectl create namespace argocd

# Install ArgoCD
kubectl apply -n argocd -f https://raw.githubusercontent.com/argoproj/argo-cd/stable/manifests/install.yaml

# Wait for ArgoCD to be ready
kubectl wait --for=condition=available --timeout=300s deployment/argocd-server -n argocd

# Get initial admin password
kubectl -n argocd get secret argocd-initial-admin-secret -o jsonpath="{.data.password}" | base64 -d

# Port forward to access UI
kubectl port-forward svc/argocd-server -n argocd 8080:443
```

## Deploy Application

```bash
# Update the repoURL in application.yaml with your GitHub repository URL

# Apply the Application CRD
kubectl apply -f argocd/application.yaml

# Check application status
kubectl get applications -n argocd
```

## Access ArgoCD UI

Access ArgoCD UI: https://localhost:8080
- Username: admin
- Password: (from secret above)

## ArgoCD Features

- **Automated Sync**: Automatically applies changes from Git
- **Self-Healing**: Reverts manual changes to match Git state
- **Pruning**: Removes resources deleted from Git
- **Multi-environment**: Can manage multiple clusters
