# Nexus-KB

### Enterprise RAG and Knowledge Graph Engine with Governed AI Workflows 🚀

Nexus-KB is an open-source reference architecture for building a production-grade enterprise Retrieval-Augmented Generation (RAG) and Knowledge Graph (KG) engine. It integrates Model Context Protocol (MCP) connectors, governed AI agent workflows, and high-availability vector search to provide a secure and auditable knowledge retrieval platform.

The workspace is structured to separate local development setups, runtime storage, and private configuration from source control. It currently contains a documentation-first design, a runnable 3-node Qdrant cluster demo, and the Phase 1 MVP python implementation.

![Python](https://img.shields.io/badge/Python-%3E%3D3.10-3776AB?style=flat-square&logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-0.115-009688?style=flat-square&logo=fastapi&logoColor=white)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-16-4169E1?style=flat-square&logo=postgresql&logoColor=white)
![Qdrant](https://img.shields.io/badge/Qdrant-v1.13-ef4444?style=flat-square&logo=qdrant&logoColor=white)
![SQLAlchemy](https://img.shields.io/badge/SQLAlchemy-2.0-red?style=flat-square&logo=sqlalchemy&logoColor=white)
![Alembic](https://img.shields.io/badge/Alembic-1.14-blue?style=flat-square&logo=alembic&logoColor=white)
![Pytest](https://img.shields.io/badge/Pytest-8.3-0A9EDC?style=flat-square&logo=pytest&logoColor=white)
![MIT License](https://img.shields.io/badge/License-MIT-green?style=flat-square)

> [!TIP]
> See also: [README-VN.md](./README-VN.md) (Phiên bản tiếng Việt) and [README-CN.md](./README-CN.md) (中文版本) for localized documentation.

---

## Table of Contents

- [Overview](#overview)
- [Key Features](#key-features)
- [System Architecture](#system-architecture)
- [Project Layout](#project-layout)
- [Configuration](#configuration)
- [Quick Start](#quick-start)
  - [1. Prerequisites](#1-prerequisites)
  - [2. Virtual Environment Setup](#2-virtual-environment-setup)
  - [3. Run Infrastructure Services](#3-run-infrastructure-services)
  - [4. Apply Database Migrations](#4-apply-database-migrations)
  - [5. Run the API Server](#5-run-the-api-server)
  - [6. Ingest Documents via CLI](#6-ingest-documents-via-cli)
  - [7. Query the Search API](#7-query-the-search-api)
- [Verification & Testing](#verification--testing)
  - [Unit Tests (Offline)](#unit-tests-offline)
  - [Integration Tests (Live Docker Services)](#integration-tests-live-docker-services)
- [Roadmap](#roadmap)
- [Contributing & Security](#contributing--security)
- [License](#license)

---

## Overview

Nexus-KB addresses the challenge of making fragmented enterprise documents (such as Confluence, markdown files, and local documentation vaults) safely searchable and queryable. It emphasizes **governed retrieval**—ensuring AI agents and search responses inherit actual user access permissions and security constraints, while keeping all access auditable.

```mermaid
flowchart TD
    %% Ingestion Flow
    SubGraph_Ingest[Ingestion Pipeline]
    Doc[Source Folder / Obsidian Vault] -->|Ingest CLI / API| Pipe[Ingestion Pipeline]
    Pipe -->|Parse Frontmatter, Tags & Links| MetaExtractor[Metadata Extractor]
    Pipe -->|Chunk & Embed BAAI/bge-m3| Embedder[Embedding Provider]
    
    MetaExtractor -->|Insert Records| DB[(PostgreSQL)]
    Embedder -->|Upsert Vectors + Payload| Qdrant[(Qdrant Vector DB)]
    
    %% Search Flow
    SubGraph_Search[Search Service]
    UserQuery[Search Query] -->|API Request| SearchAPI[Search REST Endpoint]
    SearchAPI -->|Generate Query Vector| Embedder
    SearchAPI -->|Retrieve Vector Matches| Qdrant
    Qdrant -->|Get Chunk IDs| Joiner[Hybrid Result Merger]
    Joiner -->|Join Metadata & Access Filters| DB
    DB -->|Return Audited Chunks| Output[Reranked Search Response]
```

---

## Key Features

- **Obsidian & Markdown Intelligence:** Automatically extracts YAML frontmatter, wiki-style links (`[[WikiLink]]`), tags, file extensions, and mime-type attributes during parsing.
- **Structured Metadata & Vector Coexistence:** Relational PostgreSQL is used to store document metadata, chunk records, and ingestion logs; Qdrant stores chunk vectors and metadata payloads.
- **Markdown-Aware Chunking:** Intelligently splits markdown documents while preserving section headers, heading paths, and token boundaries.
- **Hybrid Search Reranking:** Computes a hybrid score by ranking vectors and incorporating lexical overlap, section titles, and tags matching to produce precise search responses.
- **Strict Repository Boundaries:** Agent operating guidelines ([AGENTS.md](AGENTS.md)) and `.gitignore` exclude secrets, logs, raw data, model weights, and local configurations.

---

## System Architecture

The target Nexus-KB architecture operates across five layers:

```mermaid
graph TD
    User[Users & Reviewers] -->|HTTPS| WebConsole[Web & Review UI]
    WebConsole -->|REST / API| Gateway[API Gateway / Auth Service]
    Gateway -->|RBAC & Rules| Workflow[Workflow & Rule Engine]
    Workflow -->|Jobs Queue| Workers[Document Parser & Graph Workers]
    Workers -->|Model Access| LLM[LLM Gateway / Local Models]
    Workers -->|Metadata & Vector storage| Relational[(PostgreSQL)]
    Workers -->|High-Availability Vectors| VectorDB[(Qdrant HA Cluster)]
    Workers -->|Entity Graphs| GraphDB[(Neo4j / Graph Store)]
```

For a detailed roadmap of how these components are planned, see [docs/action.md](docs/action.md). For source-of-truth technical details, see [docs/architecture.md](docs/architecture.md).

---

## Project Layout

```text
nexus-kb/
├── .agents/                          # Shared local agent skills
├── .claude/                          # Claude Code project configuration
├── .codex/                           # Codex project configuration
├── .hermes/                          # Local Hermes runtime configuration
├── .rules                            # Experience Engine API guide for coding agents
├── docs/                             # Project documentation
│   ├── action.md                     # Roadmap and execution strategy
│   ├── architecture.md               # Architecture details (Source-of-Truth)
│   ├── phase1-mvp.md                 # Current Phase 1 implementation scope
│   ├── architect.md                  # Legacy redirect pointer
│   └── new.md                        # Legacy redirect pointer
├── infrastructure/                   # DB migrations and initial setup
│   ├── alembic/                      # Alembic schema migrations script
│   ├── migrations/                   # SQL init schema scripts
│   └── alembic.ini                   # Alembic configuration
├── packages/                         # Shared libraries
│   ├── shared-contracts/             # Shared Pydantic data schemas
│   └── vector-client/                # Qdrant client utility wrappers
├── qdrant-multi-node-cluster/        # 3-node HA Qdrant cluster Docker setup
├── services/                         # Backend services
│   └── nexus-api/                    # FastAPI web server and search engine
├── workers/                          # Async pipeline tasks
│   └── document-parser/              # Local file parsing and vector ingest
├── tests/                            # Unit and live integration test suites
├── requirements.txt                  # Python dependency specifications
├── pytest.ini                        # Pytest config setting path targets
├── docker-compose.yml                # Local docker compose (Postgres + Qdrant)
└── AGENTS.md                         # Rules governing AI assistants
```

---

## Configuration

The application is configured using environment variables. An example template is located in [.env.example](.env.example). Create a `.env` file in the root directory before running commands.

| Environment Variable | Default Value | Description |
|---|---|---|
| `POSTGRES_HOST` | `localhost` | PostgreSQL database hostname |
| `POSTGRES_PORT` | `5432` | PostgreSQL database port |
| `POSTGRES_DB` | `nexus_kb` | PostgreSQL database name |
| `POSTGRES_USER` | `nexus` | PostgreSQL owner username |
| `POSTGRES_PASSWORD` | `change-me` | PostgreSQL owner password |
| `POSTGRES_DSN` | `postgresql+psycopg://nexus:change-me@localhost:5432/nexus_kb` | Database connection DSN (prefer psycopg driver) |
| `QDRANT_HOST` | `localhost` | Qdrant host interface endpoint |
| `QDRANT_HTTP_PORT` | `6333` | Qdrant REST API port |
| `QDRANT_GRPC_PORT` | `6334` | Qdrant gRPC API port |
| `QDRANT_COLLECTION` | `nexus_chunks` | Destination collection name for vector shards |
| `NEXUS_EMBEDDING_MODEL` | `BAAI/bge-m3` | Embedding model HuggingFace path or local folder |
| `NEXUS_EMBEDDING_DIMENSION`| `1024` | Embedding vector output dimension |
| `NEXUS_KB_RUN_LIVE_TESTS` | `0` | Flag to execute integration tests on live containers (`0` or `1`) |

---

## Quick Start

### 1. Prerequisites

- Python 3.10 or higher installed.
- Docker and Docker Compose installed.

### 2. Virtual Environment Setup

Initialize a Python virtual environment and install dependencies:

```powershell
python -m venv .venv
# On Windows PowerShell:
.venv\Scripts\Activate.ps1
# On Linux/macOS:
# source .venv/bin/activate

pip install -r requirements.txt
```

### 3. Run Infrastructure Services

Start the localized PostgreSQL database and Qdrant vector store in the background:

```bash
docker compose up -d
```

### 4. Apply Database Migrations

Bring the database schema up-to-date using Alembic:

```powershell
alembic -c infrastructure/alembic.ini upgrade head
```

### 5. Run the API Server

Configure the `PYTHONPATH` context and run the FastAPI server using Uvicorn:

```powershell
# On Windows PowerShell:
$env:PYTHONPATH="packages/shared-contracts;packages/vector-client;workers/document-parser;services/nexus-api"
uvicorn nexus_api.main:app --reload

# On Linux/macOS:
# export PYTHONPATH="packages/shared-contracts:packages/vector-client:workers/document-parser:services/nexus-api"
# uvicorn nexus_api.main:app --reload
```

The API will now be running on `http://127.0.0.1:8000`. You can inspect the interactive OpenAPI documentation at `/docs`.

### 6. Ingest Documents via CLI

Use the ingestion worker CLI tool to parse local file folders or Obsidian vaults:

```powershell
# Set PYTHONPATH
$env:PYTHONPATH="packages/shared-contracts;packages/vector-client;workers/document-parser;services/nexus-api"

# Ingest an Obsidian vault directory
python -m nexus_document_parser.cli path\to\vault --source-type obsidian
```

### 7. Query the Search API

Search ingested chunks via REST endpoints:

```bash
curl -X POST "http://127.0.0.1:8000/api/v1/search" \
     -H "Content-Type: application/json" \
     -d '{
       "query": "governed retrieval",
       "limit": 5,
       "tags": ["rag"]
     }'
```

---

## Verification & Testing

### Unit Tests (Offline)

Run the synthetic unit tests that execute completely offline and do not require Docker containers:

```bash
python -m pytest -q
```

### Integration Tests (Live Docker Services)

To run tests against actual Postgres and Qdrant docker containers:

1. Ensure services are running: `docker compose up -d`.
2. Run migration scripts: `alembic -c infrastructure/alembic.ini upgrade head`.
3. Execute integration tests:

```powershell
# Windows PowerShell
$env:NEXUS_KB_RUN_LIVE_TESTS="1"
python -m pytest tests/test_live_integration_scaffold.py -q
```

---

## Roadmap

- **Phase 1 (Current):** Basic Python local markdown/Obsidian ingestion, PostgreSQL metadata logging, Qdrant client wrapper, FastAPI API layer, and test coverage.
- **Phase 1.5:** Advanced metadata injection, markdown section path tracking, lexical-vector hybrid reranker scoring.
- **Phase 2:** Graph Entity extractor engine, Neo4j relationship builder pipeline, core RBAC filters.
- **Phase 3:** Front-end React Web UI Dashboard console, search result explorer, and audit review workspace.

---

## Contributing & Security

Contributions are highly encouraged! Please review [CONTRIBUTING.md](CONTRIBUTING.md) to understand the workflow, and read [AGENTS.md](AGENTS.md) if you are pair-programming with AI agents.

Security issues should not be reported via public GitHub issues. Please follow the instructions in [SECURITY.md](SECURITY.md) to submit private reports.

---

## License

This project is licensed under the MIT License. See [LICENSE](LICENSE) for the full text.
