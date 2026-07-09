# Nexus-KB Deployment Quick Start

Complete stack: PostgreSQL + Qdrant + API + Web Console in one docker-compose.

## Prerequisites

- Docker & Docker Compose installed
- 4GB+ RAM, 10GB+ disk space
- Ports 5432 (PostgreSQL), 6333 (Qdrant), 8000 (API), 3000 (Web) available

## 1. Clone & Setup

```bash
git clone https://github.com/KhaiTrang1995/nexus-kb.git
cd nexus-kb

# Copy env template
cp .env.example .env

# Edit .env if needed (defaults work for local dev)
# POSTGRES_PASSWORD=your_secure_password
# LLM_ENABLED=false  # Set to true if running Ollama on host
```

## 2. Deploy with Docker Compose

```bash
# Build and start all services (takes 2-3 min first time)
docker compose -f docker-compose.prod.yml up -d

# Verify services are healthy
docker compose -f docker-compose.prod.yml ps
# Expected: postgres, qdrant, api, web all "healthy" or "Up"

# Check API health
curl http://localhost:8000/health
# {"version":"0.3.0","status":"ok",...}

# Open web console
open http://localhost:3000
# or navigate to http://localhost:3000 in browser
```

## 3. First Steps in Web Console

1. **Login**: Use mock accounts (Alice/Bob/Carol) or skip for guest access
2. **Ingest** (as Reviewer): Upload sample markdown files
3. **Search**: Semantic + vector search with graph context
4. **Review Queue** (as Reviewer): Approve low-confidence chunks
5. **Graph**: View extracted entities and relationships
6. **Audit**: See all ingestion/search/review events

## 4. Ingest Sample Data

```bash
# Using Docker exec
docker exec nexus-kb-api python -m nexus_document_parser.cli /app/data/sample_docs --source-type local

# Or from host (if venv set up)
cd core/techspherex-engine  # if using TechSphereX bridge
# ... ingestion commands
```

## 5. Configure LLM Extraction (Optional)

If you want the Phase 6 LLM Extraction Engine:

```bash
# Start Ollama (separate terminal)
ollama serve

# In another terminal, pull a model
ollama pull llama3.2:3b

# Update .env
LLM_ENABLED=true
LLM_PROVIDER=ollama
LLM_BASE_URL=http://host.docker.internal:11434  # macOS/Windows host access

# Restart API
docker compose -f docker-compose.prod.yml restart api
```

## 6. Logs & Debugging

```bash
# View API logs
docker compose -f docker-compose.prod.yml logs -f api

# View all logs
docker compose -f docker-compose.prod.yml logs -f

# Shell into API container
docker exec -it nexus-kb-api bash

# Check database
docker exec -it nexus-kb-postgres psql -U nexus -d nexus_kb -c "SELECT COUNT(*) FROM documents;"
```

## 7. Stop & Cleanup

```bash
# Stop services (keep volumes)
docker compose -f docker-compose.prod.yml down

# Stop and remove all data
docker compose -f docker-compose.prod.yml down -v

# Remove images
docker image rm nexus-kb-api nexus-kb-web
```

## Environment Variables

| Variable | Default | Description |
|---|---|---|
| `POSTGRES_PASSWORD` | `nexus_dev_password` | Database password (change in production!) |
| `POSTGRES_DB` | `nexus_kb` | Database name |
| `POSTGRES_PORT` | `5432` | PostgreSQL port |
| `QDRANT_HTTP_PORT` | `6333` | Qdrant HTTP port |
| `QDRANT_GRPC_PORT` | `6334` | Qdrant gRPC port |
| `API_PORT` | `8000` | FastAPI port |
| `WEB_PORT` | `3000` | Web console port |
| `NEXUS_EMBEDDING_MODEL` | `BAAI/bge-m3` | Embedding model (downloads ~2GB first run) |
| `LLM_ENABLED` | `false` | Enable Phase 6 LLM extraction |
| `LLM_PROVIDER` | `ollama` | `ollama` or `openai` |
| `LLM_BASE_URL` | `http://localhost:11434` | Ollama endpoint |

## Troubleshooting

**API won't start (Alembic error)**
```bash
# Restart with fresh DB
docker compose -f docker-compose.prod.yml down -v
docker compose -f docker-compose.prod.yml up -d
```

**Web console shows blank page**
- Check API health: `curl http://localhost:8000/health`
- Check browser console (F12) for errors
- Restart web service: `docker compose -f docker-compose.prod.yml restart web`

**Out of memory during embedding**
- Reduce `NEXUS_EMBEDDING_MODEL` to smaller model: `sentence-transformers/all-MiniLM-L6-v2`
- Or increase Docker memory limit

**Qdrant not starting**
- Check disk space: `docker logs nexus-kb-qdrant`
- Delete volume: `docker volume rm nexus-kb_qdrant_data`

## Architecture

```
┌─────────────────────────────────────────────────┐
│           Docker Network: nexus-network          │
├──────────────────┬──────────────────┬───────────┤
│                  │                  │           │
│   PostgreSQL     │   Qdrant Vector  │  Nginx    │
│   :5432          │   Store :6333    │  :80      │
│                  │                  │           │
│   postgres:16    │   qdrant:v1.13   │  Node.js  │
│   (Metadata)     │   (Vectors)      │  React    │
│                  │                  │           │
└──────────────────┴──────────────────┴───────────┘
                        ▲                    │
                        │ SQL/HTTP           │ HTTP
                        │                    ▼
                   ┌─────────────────────────────┐
                   │    FastAPI :8000             │
                   │   nexus-api container       │
                   │  (Document Parser, Search,  │
                   │   Review, Graph Builder)    │
                   └─────────────────────────────┘
```

## Next Steps

1. **Ingest documents** via web console or CLI
2. **Review & approve** chunks in Review Queue
3. **Search** with semantic queries
4. **Extract entities** via Graph Builder (Phase 4)
5. **Enable LLM** for automatic entity extraction (Phase 6)

## Support

- Issues: https://github.com/KhaiTrang1995/nexus-kb/issues
- Docs: `docs/architecture.md`, `docs/UI/`
- API Docs: http://localhost:8000/docs (after starting)
