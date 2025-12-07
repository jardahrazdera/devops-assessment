# Kubernetes Secrets Management

## Overview

This project uses template-based secret generation to avoid committing credentials to version control.

## How It Works

1. **Template Files** (committed to git):
   - `postgres-secret.yaml.template` - PostgreSQL credentials template
   - `app-secret.yaml.template` - Application connection strings template

2. **Generated Files** (gitignored):
   - `postgres-secret.yaml` - Actual PostgreSQL secret (generated from template)
   - `app-secret.yaml` - Actual application secret (generated from template)

3. **Automatic Generation**:
   The `scripts/deploy.sh` script automatically generates secrets from templates using `envsubst`.

## Usage

### During Deployment

The deployment script automatically generates secrets from templates:

```bash
./scripts/deploy.sh latest
```

### Custom Credentials

Set environment variables before running deploy.sh:

```bash
export POSTGRES_USER="myuser"
export POSTGRES_PASSWORD="securepassword123"
export POSTGRES_DB="mydb"
./scripts/deploy.sh latest
```

### Manual Generation

If you need to generate secrets manually:

```bash
# Set credentials
export POSTGRES_USER="devops"
export POSTGRES_PASSWORD="devops123"
export POSTGRES_DB="devopsdb"

# Generate from templates
envsubst < k8s/postgres-secret.yaml.template > k8s/postgres-secret.yaml
envsubst < k8s/app-secret.yaml.template > k8s/app-secret.yaml

# Apply to cluster
kubectl apply -f k8s/postgres-secret.yaml
kubectl apply -f k8s/app-secret.yaml
```

## Security Best Practices

### Local Development
- Use default credentials (devops/devops123) for local k3d clusters
- Secrets are generated at deployment time, never committed

### Production Environments

**DO NOT** commit actual secrets. Instead, use one of these approaches:

1. **Sealed Secrets** (Bitnami)
   - Encrypt secrets with cluster public key
   - Commit encrypted `SealedSecret` resources
   - Controller decrypts in-cluster only

2. **External Secrets Operator**
   - Sync from external stores (Vault, AWS Secrets Manager, Azure Key Vault)
   - Secrets managed outside cluster
   - Automatic rotation support

3. **SOPS** (Secrets Operations)
   - Encrypt YAML files with PGP/KMS
   - Partial encryption (only values, not keys)
   - Cloud provider KMS integration

4. **HashiCorp Vault**
   - Central secret store
   - Dynamic secret generation
   - Lease management and rotation

See [DESIGN.md](DESIGN.md) for detailed production secret management approaches.

## Required Tools

- `envsubst` - Part of the `gettext` package
  - Ubuntu/Debian: `sudo apt-get install gettext-base`
  - macOS: `brew install gettext`
  - Alpine: `apk add gettext`

## Files

| File | Purpose | Committed |
|------|---------|-----------|
| `*.yaml.template` | Secret templates with placeholders | Yes |
| `*-secret.yaml` | Generated secrets with actual credentials | No (gitignored) |
| `.gitignore` | Prevents accidental commit of secrets | Yes |
| `SECRETS.md` | This documentation | Yes |
