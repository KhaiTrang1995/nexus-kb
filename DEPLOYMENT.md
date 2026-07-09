# Nexus-KB Production Deployment

Complete guide for deploying Nexus-KB in production using Docker.

## Overview

**Stack**: PostgreSQL 16 + Qdrant + FastAPI (`api`) + FIFO ingestion worker (`worker`) + React/Nginx (`web`)

**Single Command Start**:
```bash
docker compose -f docker-compose.prod.yml up -d
```

That's it. All services auto-start, healthchecks run, migrations apply, and you're ready.

## Prerequisites

- **Hardware**: 4GB RAM, 10GB disk (scale up for large ingestions)
- **Docker**: 24.0+
- **Ports**: 5432, 6333, 6334, 8000, 3000 (configurable via `.env`)
- **Network**: Docker internal `nexus-network` bridge

## Environment Setup

Copy `.env.example` to `.env`:

```bash
cp .env.example .env
```

**Critical Variables**:

```env
# Database (change password!)
POSTGRES_PASSWORD=your_very_secure_password_here

# Embedding (2GB+ model, requires 2GB VRAM)
NEXUS_EMBEDDING_MODEL=BAAI/bge-m3

# LLM Extraction (optional)
LLM_ENABLED=false
LLM_PROVIDER=ollama
LLM_BASE_URL=http://host.docker.internal:11434  # macOS/Windows
# LLM_BASE_URL=http://localhost:11434          # Linux
```

## Deployment

### 1. Build Images

```bash
docker compose -f docker-compose.prod.yml build
# First time: ~3-5 minutes (downloads base images, installs Python packages)
```

### 2. Start Services

```bash
docker compose -f docker-compose.prod.yml up -d

# Verify all healthy
docker compose -f docker-compose.prod.yml ps
```

**Expected output**:
```
NAME                  STATUS
nexus-kb-postgres     Up (healthy)
nexus-kb-qdrant       Up (healthy)
nexus-kb-api          Up (healthy)
nexus-kb-worker       Up
nexus-kb-web          Up (healthy)
```

`worker` has no HTTP healthcheck (it's a queue consumer, not a server) -- verify it's alive with
`docker compose -f docker-compose.prod.yml logs -f worker` instead of `ps --health`.

### 3. Verify Health

```bash
# API health
curl http://localhost:8000/health
# {"version":"0.3.0","status":"ok"}

# OpenAPI docs
open http://localhost:8000/docs

# Web console
open http://localhost:3000
```

### 4. Init Data (Optional)

```bash
# Seed demo documents (Phase 1 CLI scan, admin-run, no workspace)
docker exec nexus-kb-api python -m nexus_document_parser.cli /app/data/samples --source-type local

# Or ingest from local path
docker exec -it nexus-kb-api bash
$ cd /app && python -m nexus_document_parser.cli /path/to/vault --source-type obsidian
```

For the web console's **Upload Files** flow (`POST /api/v1/documents`), an admin must first
create at least one workspace and add users to it -- uploads are workspace-scoped and fail
closed with zero visibility until that's done:

```bash
# Mint an admin dev-token (AUTH_MODE=jwt in prod requires a real login instead; see Security)
curl -X POST http://localhost:8000/api/v1/auth/dev-token \
  -H "Content-Type: application/json" \
  -d '{"user_id":"admin","name":"Admin","role":"Auditor","is_admin":true}'

# Create a workspace (use the access_token from the response above)
curl -X POST http://localhost:8000/api/v1/workspaces \
  -H "Authorization: Bearer <access_token>" -H "Content-Type: application/json" \
  -d '{"name":"Engineering","slug":"engineering"}'
```

Uploaded/synced files only get processed if the `worker` container is running -- check
`docker compose -f docker-compose.prod.yml logs -f worker` if jobs stay `queued`.

## Managing Services

### View Logs

```bash
# API logs
docker compose -f docker-compose.prod.yml logs -f api

# All logs
docker compose -f docker-compose.prod.yml logs -f

# Follow specific service
docker compose -f docker-compose.prod.yml logs -f postgres
```

### Database Access

```bash
docker exec -it nexus-kb-postgres psql -U nexus -d nexus_kb

# Run SQL
\c nexus_kb
SELECT COUNT(*) FROM documents;
SELECT COUNT(*) FROM chunks;
```

### Qdrant Console

Web UI at `http://localhost:6333/dashboard`

### Stop Services

```bash
# Keep volumes (data persists)
docker compose -f docker-compose.prod.yml down

# Remove everything
docker compose -f docker-compose.prod.yml down -v
```

## Production Recommendations

### 1. Security

- [ ] Change all default passwords (`POSTGRES_PASSWORD`, etc)
- [ ] Use strong RNG: `openssl rand -base64 32`
- [ ] Run behind reverse proxy (nginx, Traefik) with HTTPS
- [ ] Implement API authentication (JWT, OAuth)
- [ ] Use Docker secrets for sensitive data
- [ ] Restrict network access (VPN, firewall rules)

### 2. Persistence

- [ ] Mount volumes to persistent storage (not ephemeral)
- [ ] Set up automated backups: `docker exec nexus-kb-postgres pg_dump ...`
- [ ] Test restore procedure monthly
- [ ] Monitor disk usage

### 3. Monitoring

```bash
# CPU/Memory per container
docker stats

# Health checks
docker compose -f docker-compose.prod.yml ps --health

# Logs rotation
# Set in docker-compose.prod.yml:
# logging:
#   options:
#     max-size: "10m"
#     max-file: "3"
```

### 4. Scaling

**Vertical**: Increase Docker resource limits
```bash
# In docker-compose.prod.yml
services:
  api:
    deploy:
      resources:
        limits:
          cpus: '2'
          memory: 2G
```

**Horizontal**: Run multiple API instances behind load balancer
```yaml
# Not included in basic compose; use Kubernetes or Docker Swarm
```

### 5. Upgrades

```bash
# Pull latest code
git pull origin main

# Rebuild images
docker compose -f docker-compose.prod.yml build --no-cache

# Restart (migrations run automatically)
docker compose -f docker-compose.prod.yml up -d
```

## Troubleshooting

### API won't start

```bash
docker compose -f docker-compose.prod.yml logs api | grep -i error

# Common: Alembic migration failed
# Fix: Manually run migration
docker exec nexus-kb-api alembic -c infrastructure/alembic.ini upgrade head
```

### Out of memory

```bash
# Monitor before/after
docker stats

# Reduce embedding model size
# In .env: NEXUS_EMBEDDING_MODEL=sentence-transformers/all-MiniLM-L6-v2
```

### Database connection refused

```bash
# Check postgres health
docker compose -f docker-compose.prod.yml ps postgres

# Restart postgres
docker compose -f docker-compose.prod.yml restart postgres

# Verify DSN in .env
POSTGRES_DSN=postgresql+psycopg://nexus:password@postgres:5432/nexus_kb
```

### Web console returns 502

```bash
# Check API is responding
docker exec -it nexus-kb-web wget -O - http://api:8000/health

# Check nginx config
docker exec -it nexus-kb-web cat /etc/nginx/nginx.conf | grep -A 5 "upstream api"
```

## Backup & Restore

### Backup

```bash
# Database
docker exec nexus-kb-postgres pg_dump -U nexus nexus_kb > backup.sql

# Qdrant vectors (manual snapshot)
docker exec -it nexus-kb-qdrant bash
$ curl -X POST http://localhost:6333/snapshots
```

### Restore

```bash
# Database
cat backup.sql | docker exec -i nexus-kb-postgres psql -U nexus nexus_kb

# Qdrant (restore from snapshot API)
# See: https://qdrant.tech/documentation/management/backup/
```

## Performance Tuning

### PostgreSQL

```bash
# Inside postgres container
docker exec -it nexus-kb-postgres psql -U nexus -d nexus_kb

# Add indexes (if missing)
CREATE INDEX idx_documents_source_path ON documents (source_path);
CREATE INDEX idx_chunks_document_id ON chunks (document_id);
```

### Qdrant

```bash
# Tune in docker-compose.prod.yml
services:
  qdrant:
    environment:
      QDRANT__STORAGE__HNSW_INDEX__PREFER_INMEMORY: "true"
      QDRANT__STORAGE__SNAPSHOT_RECOVERY__BATCH_SIZE: "256"
```

### API

```bash
# Increase uvicorn workers in Dockerfile.api
CMD ["uvicorn", "nexus_api.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "4"]
```

## Monitoring Checklist

- [ ] All 4 containers with healthchecks (`postgres`, `qdrant`, `api`, `web`) show `(healthy)`; `worker` shows `Up` and its logs show poll activity, not repeated tracebacks
- [ ] API responds to `GET /health` in < 100ms
- [ ] Web console loads without JS errors (F12)
- [ ] Database has documents/chunks ingested
- [ ] Qdrant collection is populated
- [ ] Logs show no ERROR or WARNING entries
- [ ] Disk usage < 80% of available
- [ ] CPU usage < 60% at rest
- [ ] Memory usage < 50% of allocated

## Support

- Issues: https://github.com/KhaiTrang1995/nexus-kb/issues
- OpenAPI docs: http://localhost:8000/docs
- Architecture: `docs/architecture.md`
