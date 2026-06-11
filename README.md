# Nexus-KB

Enterprise RAG and Knowledge Graph Engine with governed AI workflows.

Nexus-KB is an open-source reference architecture for building a secure Retrieval-Augmented Generation (RAG) and Knowledge Graph (KG) platform. It combines local and Obsidian ingestion, PostgreSQL metadata and audit storage, Qdrant vector search, MCP source connector boundaries, review workflows, graph construction, and an LLM Gateway slice.

The repository is still a reference implementation, not a production-ready enterprise stack. All examples and tests use synthetic data.

![Python](https://img.shields.io/badge/Python-%3E%3D3.10-3776AB?style=flat-square&logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-0.115-009688?style=flat-square&logo=fastapi&logoColor=white)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-16-4169E1?style=flat-square&logo=postgresql&logoColor=white)
![Qdrant](https://img.shields.io/badge/Qdrant-v1.13-ef4444?style=flat-square&logo=qdrant&logoColor=white)
![SQLAlchemy](https://img.shields.io/badge/SQLAlchemy-2.0-red?style=flat-square&logo=sqlalchemy&logoColor=white)
![Alembic](https://img.shields.io/badge/Alembic-1.14-blue?style=flat-square&logo=alembic&logoColor=white)
![Pytest](https://img.shields.io/badge/Pytest-8.3-0A9EDC?style=flat-square&logo=pytest&logoColor=white)
![MIT License](https://img.shields.io/badge/License-MIT-green?style=flat-square)

See also [README-VN.md](./README-VN.md) and [README-CN.md](./README-CN.md) for localized documentation.

## Overview

Nexus-KB addresses fragmented enterprise knowledge by making documents searchable, reviewable, auditable, and graph-aware. The current codebase implements a local MVP path:

- Parse local and Obsidian markdown documents.
- Extract frontmatter, tags, wikilinks, section paths, and mime/file metadata.
- Chunk, embed, and index approved content in Qdrant.
- Store documents, chunks, ingestion runs, audit logs, review items, and graph records in PostgreSQL.
- Search with vector retrieval, metadata filters, lexical reranking, snippets, and optional graph context.
- Route low-confidence chunks through a human review queue.
- Expose a Confluence-oriented MCP connector scaffold.
- Build relational Knowledge Graph entities and relationships from approved chunks.
- Test an LLM Gateway slice with routing, caching, retry, telemetry, and provider abstraction.

## Architecture

```mermaid
flowchart TD
    Source[Local files / Obsidian / MCP source] --> Parser[Document Parser Worker]
    Parser --> Review{Review policy}
    Review -->|Approved / direct commit| Metadata[(PostgreSQL)]
    Review -->|Approved / direct commit| Vector[(Qdrant)]
    Review -->|Low confidence| Queue[Review Queue]
    Queue -->|Approve / modify| Metadata
    Queue -->|Approve / modify| Vector
    Metadata --> Graph[Graph Builder Worker]
    Graph --> GraphTables[(Relational graph tables)]
    API[FastAPI] --> Metadata
    API --> Vector
    API --> GraphTables
    API --> Audit[(Audit logs)]
```

The source-of-truth architecture document is [docs/architecture.md](docs/architecture.md). The roadmap is [docs/action.md](docs/action.md). Agent phase handoff and completion checks are tracked in [docs/phase-checklist.md](docs/phase-checklist.md).

## Features

- **Ingestion MVP:** Local and Obsidian markdown ingestion, frontmatter/tag/wikilink extraction, markdown-aware chunking, deterministic test embeddings, and runtime sentence-transformer embeddings.
- **Hybrid Retrieval:** Qdrant vector search with PostgreSQL metadata joins, tag/source filters, lexical reranking, snippets, and graph context fields.
- **Audit and Review:** Immutable audit events for ingestion, document reads, chunk generation, search, and review actions. Review queue supports approve, reject, and modify flows with mock reviewer RBAC.
- **MCP Source Connector:** `mcp-servers/confluence-bridge` provides source discovery and document read tools with user-context authorization, disabled mutating tools, structured errors, and redaction.
- **Knowledge Graph Builder:** `workers/graph-builder` extracts entities and relationships from approved chunks, merges duplicates, stores confidence/provenance, and supports chunk-level graph lookup.
- **LLM Gateway Slice:** `services/llm-gateway` centralizes routing, prompt categories, caching, retry, telemetry, and provider abstraction for future model use.
- **Repository Safety:** `.gitignore`, [AGENTS.md](AGENTS.md), and `.rules` keep secrets, logs, raw data, sessions, model files, vector snapshots, and local runtime state out of git.

## Project Layout

```text
nexus-kb/
|-- docs/                            # Architecture, roadmap, and phase plans
|-- infrastructure/
|   |-- alembic/                     # Alembic migration environment
|   |-- migrations/                  # SQL init scripts for local containers
|   `-- alembic.ini
|-- mcp-servers/
|   `-- confluence-bridge/           # Phase 3 MCP source connector scaffold
|-- packages/
|   |-- shared-contracts/            # Shared Pydantic schemas
|   `-- vector-client/               # Qdrant client wrapper
|-- qdrant-multi-node-cluster/       # 3-node HA Qdrant demo
|-- services/
|   |-- llm-gateway/                 # Phase 5 gateway slice
|   `-- nexus-api/                   # FastAPI ingest/search/audit/review/graph API
|-- workers/
|   |-- document-parser/             # Parsing, chunking, embedding, ingest
|   `-- graph-builder/               # Entity and relationship builder
|-- tests/                           # Offline and live tests
|-- docker-compose.yml               # Local Postgres + Qdrant
|-- requirements.txt
|-- pytest.ini
`-- AGENTS.md
```

## Configuration

Create `.env` from [.env.example](.env.example) when running local services.

| Variable | Default | Description |
|---|---|---|
| `POSTGRES_HOST` | `localhost` | PostgreSQL host |
| `POSTGRES_PORT` | `5432` | PostgreSQL port |
| `POSTGRES_DB` | `nexus_kb` | Database name |
| `POSTGRES_USER` | `nexus` | Database user |
| `POSTGRES_PASSWORD` | `change-me` | Database password |
| `POSTGRES_DSN` | `postgresql+psycopg://nexus:change-me@localhost:5432/nexus_kb` | SQLAlchemy DSN |
| `QDRANT_HOST` | `localhost` | Qdrant host |
| `QDRANT_HTTP_PORT` | `6333` | Qdrant HTTP port |
| `QDRANT_GRPC_PORT` | `6334` | Qdrant gRPC port |
| `QDRANT_COLLECTION` | `nexus_chunks` | Vector collection |
| `NEXUS_EMBEDDING_MODEL` | `BAAI/bge-m3` | Runtime embedding model |
| `NEXUS_EMBEDDING_DIMENSION` | `1024` | Embedding dimension |
| `NEXUS_KB_RUN_LIVE_TESTS` | `0` | Enables live Docker-backed tests |

## Quick Start

### 1. Install dependencies

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

Linux/macOS:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 2. Start local storage

```bash
docker compose up -d
```

### 3. Apply migrations

```powershell
alembic -c infrastructure/alembic.ini upgrade head
```

If your Compose database was initialized from SQL scripts before Alembic versioning existed, stamp Phase 1 first:

```powershell
alembic -c infrastructure/alembic.ini stamp 001_phase1_schema
alembic -c infrastructure/alembic.ini upgrade head
```

### 4. Run the API

PowerShell:

```powershell
$env:PYTHONPATH="packages/shared-contracts;packages/vector-client;workers/document-parser;workers/graph-builder;services/nexus-api"
uvicorn nexus_api.main:app --reload
```

Linux/macOS:

```bash
export PYTHONPATH="packages/shared-contracts:packages/vector-client:workers/document-parser:workers/graph-builder:services/nexus-api"
uvicorn nexus_api.main:app --reload
```

Open `http://127.0.0.1:8000/docs`.

### 5. Ingest documents

```powershell
$env:PYTHONPATH="packages/shared-contracts;packages/vector-client;workers/document-parser;workers/graph-builder;services/nexus-api"
python -m nexus_document_parser.cli path\to\vault --source-type obsidian
```

### 6. Search

```bash
curl -X POST "http://127.0.0.1:8000/api/v1/search" \
  -H "Content-Type: application/json" \
  -d '{"query":"governed retrieval","limit":5,"tags":["rag"]}'
```

### 7. Audit, review, and graph

```bash
curl "http://127.0.0.1:8000/api/v1/audit?limit=20"

curl "http://127.0.0.1:8000/api/v1/review/queue" \
  -H "X-User-Role: Reviewer"

curl -X POST "http://127.0.0.1:8000/api/v1/graph/build?limit=100"
```

### 8. MCP connector runner

```powershell
$env:PYTHONPATH="mcp-servers/confluence-bridge"
'{"tool":"confluence.discover_sources","arguments":{"actor":{"user_id":"alice","roles":["SourceReader"],"allowed_spaces":["KB"],"correlation_id":"demo"},"space_key":"KB"}}' | python -m nexus_confluence_bridge
```

## Verification

Offline tests:

```bash
python -m pytest -q
```

Live tests with Docker services:

```powershell
$env:NEXUS_KB_RUN_LIVE_TESTS="1"
$env:POSTGRES_DSN="postgresql://nexus:nexus_dev_password@localhost:5432/nexus_kb"
python -m pytest tests/test_live_integration_scaffold.py tests/test_live_graph_repository.py -q
```

## Roadmap Status

- **Phase 0:** Documentation, architecture source-of-truth, agent rules, and repository safety baseline. (Complete)
- **Phase 1 / 1.5:** Local and Obsidian ingestion, PostgreSQL metadata, Qdrant vectors, markdown-aware chunking, hybrid reranking, snippets, and tests. (Local MVP complete; offline + live tests pass)
- **Phase 2:** Audit logs, review queue, review actions, mock reviewer RBAC, and audit/review APIs. (Local MVP complete; full port contracts, psycopg/SQLAlchemy parity, explicit calls; tests pass)
- **Phase 3:** Confluence-oriented MCP source connector scaffold with source discovery, document read, user-context authorization, disabled mutating tools, and redacted errors. (Scaffold + tests complete)
- **Phase 4:** Knowledge Graph builder with entity extraction, duplicate merge, relationship confidence/provenance, relational graph tables, graph APIs, and search result graph context. (Local MVP complete; tests + live graph repository pass)
- **Phase 5:** LLM Gateway slice with routing, prompt category tracking, caching, retry, telemetry, and provider abstraction. (Slice complete + tests)

See `docs/frontend-plan.md` (new) for the UI / web-console architecture plan and Mermaid diagrams targeting the `apps/web-console/` placeholder (search + graph context, review queue/actions, audit viewer, ingestion status, per `architecture.md` UI Layer).

Future work remains for production authentication, a full web console implementation, production API gateway, real enterprise connector adapters, deployment hardening, and observability. All examples and tests use synthetic data only.

## Contributing and Security

Read [CONTRIBUTING.md](CONTRIBUTING.md), [SECURITY.md](SECURITY.md), and [AGENTS.md](AGENTS.md) before contributing. Do not commit credentials, internal hostnames, customer data, logs, local sessions, model files, vector snapshots, or audit exports.

## License

This project is licensed under the MIT License. See [LICENSE](LICENSE).
