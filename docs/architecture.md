# Architecture

Enterprise Knowledge Hub is designed as a modular knowledge platform for enterprise document ingestion, retrieval augmented generation, knowledge graph construction, and governed AI workflows. Nexus-KB is the implementation name for this architecture.

Related documents:

- [action.md](action.md): strategy, roadmap, and execution plan.
- [phase-checklist.md](phase-checklist.md): phase completion gates and verification evidence.

## Design Principles

- Keep source connectors, AI processing, storage, and review workflows separated by explicit service boundaries.
- Treat authorization and audit as mandatory platform concerns, not optional add-ons.
- Keep LLM access behind a gateway that centralizes routing, caching, retries, cost controls, and observability.
- Store raw documents, model files, vector snapshots, and runtime logs outside git.
- Design for local development first, then promote to production deployment through reproducible infrastructure.

## Target System Context

```mermaid
flowchart LR
    Users[Users and Reviewers] --> UI[Web UI and Review Console]
    UI --> API[API Gateway]
    API --> Auth[RBAC and Policy Service]
    API --> Workflow[Workflow and Rule Engine]
    Workflow --> Queue[Job Queue]
    Queue --> Parser[Document Parser Worker]
    Queue --> Graph[Graph Builder Worker]
    Parser --> MCP[MCP Connector Hub]
    MCP --> Sources[Enterprise Sources]
    Parser --> LLM[LLM Gateway]
    Graph --> LLM
    LLM --> Models[Local Models and External APIs]
    Parser --> Storage[Storage Layer]
    Graph --> Storage
    API --> Storage
```

## Layers

### UI Layer

The UI provides search, graph exploration, ingestion status, audit review, and human approval workflows. The first implementation should favor a compact operational interface over a marketing-style landing page.

### Backend Layer

Backend services own API contracts, authentication, authorization, workflow state, audit records, and metadata. Services should be independently testable and should not directly embed LLM prompt logic.

### Orchestration Layer

The queue layer dispatches long-running ingestion and graph-building work. Jobs should carry correlation IDs, actor context, source document metadata, and policy decisions needed for audit.

### AI Processing Layer

Workers parse documents, split content into chunks, extract entities, build candidate relationships, and request LLM assistance through the LLM Gateway. Workers must not call external models directly unless routed through the gateway.

### MCP Connector Layer

MCP connectors expose controlled access to systems such as Confluence, internal databases, or document repositories. Connectors must enforce user context and least-privilege access.

### Storage Layer

Recommended storage responsibilities:

- PostgreSQL or SQL Server for metadata, workflow state, audit logs, and policy records.
- Qdrant for vector search.
- Neo4j, ArangoDB, or a relational graph model for entity relationships.
- Object storage or NAS for raw documents and model files.

## Processing Flow

1. Ingest request is created with user context and source metadata.
2. RBAC and source access checks run before any document read.
3. Rule Engine selects parsing strategy, model tier, review requirements, and priority.
4. Parser worker chunks content and extracts structured candidates.
5. Reducer merges duplicates and resolves conflicting candidates.
6. Human review or automated policy review approves, edits, or rejects results.
7. Verified content is committed to metadata storage, vector index, and graph storage.
8. Audit records capture actor, source, model, prompt category, result confidence, and storage IDs.

## Implementation Status

This section maps the target architecture to what is actually implemented in the repository. It is the bridge between this document and [phase-checklist.md](phase-checklist.md). The roadmap and phase intent are tracked in [action.md](action.md).

| Architecture layer | Status | Implemented module |
| --- | --- | --- |
| UI Layer | Implemented | `apps/web-console` (React + Vite + Tailwind operational console) |
| Backend Layer | Implemented | `services/nexus-api` (modular routers: ingest, search, audit, review, graph, auth, deliberate) |
| Authentication | Implemented | JWT auth module (`services/nexus-api/nexus_api/auth/`) with dev and production modes |
| Authorization | Implemented | Server-side RBAC via FastAPI `Depends()` on all privileged endpoints |
| Orchestration Layer | Planned | None yet (ingestion runs in-process) |
| AI Processing Layer | Implemented MVP | `workers/document-parser` (markdown/text + markitdown-based PDF/DOCX/XLSX/PPTX/CSV conversion), `workers/graph-builder` |
| LLM Gateway | Implemented slice | `services/llm-gateway` |
| MCP Connector Layer | Implemented scaffold | `mcp-servers/confluence-bridge` |
| Storage Layer | Implemented MVP | PostgreSQL via Alembic migrations, Qdrant via `packages/vector-client` |
| Shared Contracts | Implemented | `packages/shared-contracts` (typed API models, response envelope) |

Audit and human review are implemented in `services/nexus-api/nexus_api/audit.py` and `review.py`. Knowledge Graph tables and APIs are implemented through migration `003_add_graph_tables.py`. Correlation ID middleware emits `X-Request-Id` on all responses.

## Monorepo Structure

Implemented today:

```text
apps/
|-- web-console/                 # React + Vite operational console (search, review, graph, audit, ingest)

services/
|-- nexus-api/                   # FastAPI backend with modular routers and JWT auth
|   |-- nexus_api/routers/       # Domain routers (search, ingest, review, graph, audit, auth, deliberate)
|   |-- nexus_api/auth/          # JWT token create/decode, auth dependencies, RBAC
|-- llm-gateway/                 # Model routing, caching, retries, and telemetry slice

workers/
|-- document-parser/             # Parsing, chunking, and embedding
|-- graph-builder/               # Entity merge and relationship construction

mcp-servers/
|-- confluence-bridge/           # Controlled Confluence access scaffold

packages/
|-- shared-contracts/            # API schemas, response envelope, and shared types
|-- vector-client/               # Qdrant client wrapper

infrastructure/
|-- alembic/                     # Alembic migration environment and versions
|-- migrations/                  # SQL init scripts for local containers
```

Planned, not yet implemented (create only when the corresponding phase begins; see [action.md](action.md)):

```text
services/
|-- api-gateway/                 # Production API boundary and request orchestration
|-- rule-engine/                 # Workflow routing and model selection

mcp-servers/
|-- internal-db-bridge/          # Controlled legacy database access (Phase 10)

packages/
|-- audit-client/                # Audit event helpers

infrastructure/
|-- observability/               # Metrics, dashboards, and alerts (Phase 11)
```

Until a planned directory is implemented, keep it out of git or preserve an intentional placeholder with `.gitkeep`.

## Security and Compliance

- Every read from an enterprise source must be authorized with the requesting actor's context.
- Sensitive document processing must create immutable audit events.
- Prompt templates must avoid embedding secrets or private configuration.
- Logs must not include raw document content unless explicitly approved for a secure environment.
- Any public sample must use synthetic data.

## Deployment Notes

Local development can use Docker Compose. Production should use isolated networks, secret management, TLS, backup policy, and observability for all storage and queue components.

The existing `qdrant-multi-node-cluster/` directory is a demo for the vector database layer, not the full platform implementation.
