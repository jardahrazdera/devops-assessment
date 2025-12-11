# Design Decisions and Rationale

This document explains the architectural choices, trade-offs, and design decisions made in this DevOps assessment project.

---

## Tool Choices

### Why FastAPI?

**Decision:** Use FastAPI for the REST API application.

**Rationale:**
- **Modern Python framework** with automatic OpenAPI/Swagger documentation
- **Type hints and validation** using Pydantic reduce runtime errors
- **High performance** comparable to Node.js and Go
- **Async support** out of the box for scalability
- **Easy Prometheus integration** via fastapi-instrumentator

**Trade-offs:**
- ✅ Developer productivity and type safety
- ✅ Automatic API documentation
- ❌ Slightly more complex than Flask for simple apps
- ❌ Smaller ecosystem than Flask (but growing fast)

---

### Why k3d (k3s in Docker)?

**Decision:** Use k3d for local Kubernetes cluster.

**Rationale:**
- **Lightweight** - k3s is a certified Kubernetes distribution with <100MB binary
- **Fast startup** - Cluster ready in seconds vs minutes with minikube
- **Docker-native** - Runs in containers, easy cleanup with `k3d cluster delete`
- **NodePort mapping** - Simple port forwarding with `-p` flags
- **Production-like** - k3s is used in edge/IoT production environments

**Trade-offs:**
- ✅ Fast and lightweight (perfect for local dev)
- ✅ Easy multi-cluster management
- ❌ Less feature-complete than full Kubernetes (but sufficient for assessment)
- ❌ Some advanced features disabled by default

**Alternatives considered:**
- **minikube**: More features but slower startup and higher resource usage
- **kind**: Similar to k3d but k3d has better performance and simpler port mapping
- **Docker Desktop K8s**: Platform-specific, harder to version

---

### Why ArgoCD for GitOps?

**Decision:** Use ArgoCD for GitOps-based deployment.

**Rationale:**
- **Declarative GitOps** - Git as single source of truth
- **Automatic sync** - Detects repository changes and applies them
- **Visual dashboard** - Easy to see sync status and application health
- **Kubernetes-native** - Understands K8s resources deeply
- **Self-healing** - Reverts manual cluster changes to match Git state

**Trade-offs:**
- ✅ Eliminates manual `kubectl apply` workflows
- ✅ Full audit trail of changes via Git history
- ✅ Easy rollback to previous Git commits
- ❌ Adds complexity for simple deployments
- ❌ ~500MB of images to install

**Implementation:**
- **Automated**: Use `./scripts/deploy.sh --argocd` for one-command deployment
- **Manual**: Install ArgoCD separately and apply `argocd/application.yaml`

**Alternatives considered:**
- **Flux**: More lightweight but less visual
- **Manual kubectl**: Simple but no GitOps benefits

---

### Why PostgreSQL (+ Redis)?

**Decision:** Use PostgreSQL for persistent data storage and Redis for caching.

**Rationale:**
- **PostgreSQL:**
  - **ACID compliance** - Data integrity guarantees
  - **JSONB support** - Flexible schema for /data endpoint
  - **Battle-tested** - Industry standard relational database
  - **Requirement alignment** - Assignment specified PostgreSQL/MySQL
  - **Persistent storage** - Uses PersistentVolumeClaim (1Gi) for data durability

- **Redis (implemented):**
  - **High-performance caching** - In-memory key-value store with 60s TTL
  - **Cache-aside pattern** - Fetch from DB on miss, populate cache
  - **Cache invalidation** - Automatic invalidation on POST operations
  - **Graceful degradation** - Application works even if Redis unavailable

**Trade-offs:**
- ✅ Production-realistic architecture with proper caching layer
- ✅ Demonstrates understanding of persistence vs caching
- ✅ Significantly improves read performance
- ❌ More complex than in-memory storage
- ❌ Requires database migrations in real projects

**Why not Redis alone?**
- Redis is best for caching/ephemeral data, not primary persistent storage
- PostgreSQL provides ACID guarantees and complex queries

---

### Why Multi-Stage Docker Builds?

**Decision:** Use multi-stage Dockerfile with separate builder and runtime stages.

**Rationale:**
- **Smaller images** - Build tools not included in final image
- **Security** - Attack surface reduced (no gcc, build deps)
- **Build cache** - Dependencies layer cached separately from app code
- **Performance** - Faster image pulls and deployments

**Trade-offs:**
- ✅ Production-grade images (~200MB vs ~800MB)
- ✅ Faster CI/CD pipelines (layer caching)
- ❌ Slightly more complex Dockerfile
- ❌ Longer initial builds (but cached after first build)

---

### Why `python:3.11-slim` (vs Alpine)?

**Decision:** Use `python:3.11-slim` as the base image for the application.

**Rationale:**
- **Compatibility:** `python-slim` images are based on Debian, offering broader compatibility with Python packages that may have C extensions. Alpine, using musl libc, can sometimes lead to runtime issues or require recompilation of certain packages.
- **Image Size:** While Alpine is generally smaller, `python:3.11-slim` still provides a significantly reduced image size compared to full Debian images, and the multi-stage build further optimizes this.
- **Maintainability:** Debian-based images often have more straightforward package management and troubleshooting due to wider community support.

**Trade-offs:**
- ✅ Broader package compatibility, reducing potential runtime errors.
- ✅ Good balance between image size and compatibility.
- ❌ Slightly larger image size compared to Alpine (though offset by multi-stage build).
- ❌ Alpine was specifically recommended in the requirements, making this a documented deviation.

---

### Why Hardcoded `latest` Tag (Local Development)?

**Decision:** Use hardcoded `latest` tag for Docker images in local k3d deployments.

**Rationale:**
- **Simplicity** - Local development environment doesn't need version management
- **Rapid iteration** - Rebuild and redeploy without tag coordination between script and manifests
- **Single source of truth** - Image tag defined once in deployment manifests
- **k3d context** - Local cluster with `imagePullPolicy: IfNotPresent` doesn't need remote registry

**Trade-offs:**
- ✅ Simplified deployment script (no parameter passing)
- ✅ No manifest templating required (envsubst, Kustomize, Helm)
- ✅ Faster local dev cycle
- ❌ Not production-appropriate (see below)

**Production considerations:**
In real production environments, you would:
- **Semantic versioning** - Use `v1.2.3` tags for releases
- **SHA tags** - Immutable references like `sha-abc1234` for exact traceability
- **Image promotion** - Move same image through dev → staging → prod
- **Registry scanning** - Automated vulnerability scanning on tagged images
- **Rollback capability** - Point to specific known-good versions

The `latest` tag is appropriate here because:
1. This is a **local assessment environment**, not production
2. Images are built and loaded directly into k3d (no remote registry)
3. Simplifies the evaluation workflow

---

### Why Prometheus + Grafana?

**Decision:** Use Prometheus for metrics and Grafana for visualization.

**Rationale:**
- **Industry standard** - De facto monitoring stack for Kubernetes
- **Pull-based** - Prometheus scrapes metrics (better for ephemeral pods)
- **PromQL** - Powerful query language for metrics
- **Kubernetes integration** - Service discovery for pod scraping
- **Open source** - No vendor lock-in

**Trade-offs:**
- ✅ Complete observability stack
- ✅ Pre-built dashboards available
- ✅ Integrates with alerting (future)
- ❌ Requires more resources than simple logging
- ❌ Learning curve for PromQL

**Alternatives considered:**
- **DataDog/New Relic**: Great but requires external account/costs
- **Logs only**: Insufficient for performance monitoring

---

## Architecture Rationale

### 2-Replica Deployment

**Decision:** Deploy application with 2 replicas.

**Rationale:**
- **High availability** - One pod can fail without downtime
- **Load distribution** - Traffic spreads across pods
- **Rolling updates** - Zero-downtime deployments
- **Resource balance** - Not wasteful for local dev, realistic for production

**Why not 1 replica?**
- Single point of failure
- Downtime during updates

**Why not 3+ replicas?**
- Overkill for local k3d cluster
- Wastes laptop resources
- 2 is minimum for HA

---

### Pod Disruption Budget (PDB)

**Decision:** Implement PDB with `minAvailable: 1` for the application.

**Rationale:**
- **Voluntary disruption protection** - Prevents simultaneous eviction of all pods during node drains, cluster upgrades, or maintenance
- **High availability guarantee** - At least 1 pod remains running during planned disruptions
- **Controlled rolling updates** - Kubernetes respects PDB during deployments
- **Production-ready** - Standard practice for critical services

**Configuration:**
- `minAvailable: 1` - At least 1 pod must always be available
- With 2 replicas, allows disruption of 1 pod at a time
- Applies only to voluntary disruptions (not node failures or OOM kills)

**What PDB protects against:**
- `kubectl drain` operations
- Cluster autoscaler evictions
- Manual pod evictions
- Preemption by higher-priority pods

**What PDB does NOT protect against:**
- Node crashes (involuntary disruptions)
- Pod crashes or OOM kills
- Application bugs

---

### NodePort vs LoadBalancer

**Decision:** Use NodePort for local development.

**Rationale:**
- **Local compatibility** - LoadBalancer requires cloud provider
- **Simple port mapping** - k3d `-p` flag maps NodePorts to localhost
- **No external dependencies** - Works without MetalLB or cloud
- **Predictable ports** - 30080, 30090, 30030 in documentation

**Production change:**
- Use `type: LoadBalancer` with cloud provider (AWS ELB, GCP LB)
- Or Ingress controller (nginx-ingress, Traefik) with TLS

---

### Resource Limits

**Decision:** Set CPU and memory requests/limits on all pods.

**Rationale:**
- **Prevents resource starvation** - One pod can't consume all cluster resources
- **Kubernetes scheduling** - Scheduler uses requests for pod placement
- **Quality of Service** - Guaranteed QoS for critical pods
- **Production readiness** - Required for realistic cluster behavior

**Values chosen:**
- **App**: 100m CPU request, 200m limit, 128Mi-256Mi memory
  - Lightweight API, minimal processing
- **PostgreSQL**: 100m-500m CPU, 256Mi-512Mi memory
  - Database needs more resources than app
- **Redis**: 50m-100m CPU, 64Mi-128Mi memory
  - Lightweight caching layer, in-memory operations
- **Prometheus**: 100m-200m CPU, 256Mi-512Mi memory
  - Metrics storage grows over time

---

### Liveness vs Readiness Probes

**Decision:** Implement both probe types on all deployments.

**Rationale:**
- **Liveness**: Restart unhealthy pods (e.g., deadlock, OOM)
- **Readiness**: Remove pod from service during startup/maintenance
- **Different delays**: Readiness 5s (fast start), Liveness 10s (avoid flapping)
- **Production safety**: Prevents routing traffic to broken pods

**Configuration:**
- App: GET /health endpoint (lightweight)
- PostgreSQL: `pg_isready -U devops` (official health check)
- Prometheus: HTTP /-/healthy (built-in)

---

## What Would Change With More Time

### 1. Secret Management Implemented

**Current Implementation:**

**Kubernetes:**
- **Kubernetes Secrets**: Separated from ConfigMaps
  - `postgres-secret.yaml`: PostgreSQL credentials (POSTGRES_USER, POSTGRES_PASSWORD, POSTGRES_DB)
  - `app-secret.yaml`: Application secrets (DATABASE_URL, REDIS_URL with credentials)
- **ConfigMaps**: Only non-sensitive configuration (log_level, environment)
- **Separation of concerns**: Secrets mounted as environment variables via `secretKeyRef`

**Docker Compose:**
- **.env file**: All sensitive values in gitignored `.env` file
- **.env.example**: Template committed to repository
- **Environment variable substitution**: `${POSTGRES_PASSWORD}` syntax in docker-compose.yml

**Security Practices:**
- ✅ Secrets separated from application configuration
- ✅ .env files gitignored (not committed)
- ✅ .env.example provides template without actual credentials
- ✅ Kubernetes Secrets use base64 encoding (K8s standard)
- ⚠️ Demo credentials committed for assessment purposes (documented in .gitignore)

**Production Improvements:**

For production environments, implement encrypted secret management:

1. **Sealed Secrets** (Bitnami)
   - Encrypt secrets with cluster public key
   - Commit encrypted SealedSecret resources to Git
   - Controller decrypts in-cluster only
   - GitOps-friendly, secrets encrypted at rest in Git

2. **External Secrets Operator**
   - Sync from external secret stores (Vault, AWS Secrets Manager, Azure Key Vault)
   - Secrets managed outside cluster
   - Automatic rotation support
   - Centralized secret management across clusters

3. **SOPS (Secrets Operations)**
   - Encrypt YAML files with PGP/KMS
   - Partial encryption (only secret values, not keys)
   - Works with existing Git workflows
   - Cloud provider KMS integration

4. **Vault Integration**
   - HashiCorp Vault as central secret store
   - Dynamic secret generation
   - Lease management and rotation
   - Audit logging

**Why Demo Approach:**
- Assessment requires working solution without external dependencies
- Demonstrates understanding of secret separation
- Shows K8s Secret resource usage
- Documents production path without requiring Vault/KMS setup

---

### 2. Helm Charts (Templates)

**Decision:** Provide Helm Charts alongside Raw Manifests but stick to Raw Manifests for the assessment demonstration.

**Implementation:**
- **Raw Manifests (`k8s/`)**: Used for the primary deployment to keep the assessment simple and explicit.
- **Helm Chart (`charts/`)**: A complete Helm chart is provided in the `charts/` directory.
  - **Templating**: Ready for multi-environment usage.
  - **Structure**: Follows standard Helm best practices.

**Why this approach?**
- **Demonstrates Skill**: Including the chart proves knowledge of Helm packaging and templating.
- **Avoids Complexity**: Wiring up a hybrid deployment script for a local assessment adds unnecessary overhead.
- **Future-Proofing**: The project is ready to be migrated to Helm-only for production.

---

### 3. Multi-Environment Support

**Current:** Single environment (development)

**Improvement:**
- **Kustomize overlays**: base/ + overlays/{dev,staging,prod}
- **Different configs**: Resource limits, replica counts per env
- **Namespaces**: Separate namespaces per environment
- **Separate databases**: Prod gets managed PostgreSQL (RDS/CloudSQL)

**Why not now?**
- Local k3d cluster = single environment
- Would demonstrate but not add functional value

---

### 4. Complete CI/CD Pipeline

**Current:** GitHub Actions simulates deployment

**Improvement:**
- **Image registry**: Push to GHCR/DockerHub with SHA tags
- **Manifest updates**: Bot commits to update image tags in Git
- **ArgoCD sync**: Auto-deploys new version
- **Integration tests**: Post-deployment smoke tests
- **Rollback automation**: Auto-rollback on failure

**Why not now?**
- Requires public registry and credentials
- Local k3d not accessible from GitHub Actions
- Assessment scope: demonstrate understanding, not full automation

---

### 5. Observability Enhancements

**Current:** Prometheus metrics + Grafana dashboards

**Improvement:**
- **Distributed tracing**: Jaeger or Tempo for request flows
- **Structured logging**: ELK or Loki stack for log aggregation
- **Alerting**: AlertManager with PagerDuty/Slack integration
- **SLOs/SLIs**: Service-level objectives and error budgets

**Why not now?**
- Monitoring stack already exceeds basic requirements
- Time-boxed assessment (4-6 hours suggested)

---

### 6. Database Migrations

**Current:** `CREATE TABLE IF NOT EXISTS` on app startup

**Improvement:**
- **Alembic**: Proper migration framework for schema changes
- **Init containers**: Run migrations before app starts
- **Versioned migrations**: Rollback support
- **Seed data**: Test fixtures for development

**Why not now?**
- Simple schema doesn't require complex migrations
- Demonstrates database integration without over-engineering

---

### 7. Security Hardening

**Current:** Basic security (non-root containers, minimal images)

**Improvement:**
- **Pod Security Standards**: Enforce restricted PSS
- **Network Policies**: Limit pod-to-pod communication
- **RBAC**: Least-privilege service accounts
- **Image signing**: Cosign/Notary for supply chain security
- **Runtime security**: Falco for anomaly detection

**Why not now?**
- Assessment already includes Trivy security scanning
- Demonstrates awareness without overwhelming the evaluation

---

### 8. Performance Optimization

**Current:** Default configurations

**Improvement:**
- **HTTP/2**: Enable for gRPC-like performance
- **Connection pooling**: PostgreSQL connection pool (pgbouncer)
- **Redis caching**: Implemented with cache-aside pattern, 60s TTL, cache invalidation
- **CDN**: Static assets via CloudFront/Cloudflare
- **Horizontal Pod Autoscaling**: Scale based on CPU/memory/custom metrics

**Why not now?**
- Demo app has no performance requirements
- Would add complexity without demonstrable benefit

---

## Conclusion

This project balances **completeness** with **clarity**. Each decision prioritizes:

1. **Production principles** - Architecture scales beyond local dev
2. **Best practices** - Follows industry standards (12-factor, GitOps)
3. **Demonstrable skills** - Shows understanding of DevOps fundamentals
4. **Practical scope** - Avoids over-engineering for assessment context

The "What Would Change" section shows awareness of production requirements while respecting time constraints. Real projects would iterate on these foundations.

---

**Last Updated:** 2025-12-08
