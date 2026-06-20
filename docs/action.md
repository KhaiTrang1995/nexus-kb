# Nexus-KB Action Plan

Nexus-KB is the planned product name for this repository: an Enterprise RAG and Knowledge Graph Engine for governed document intelligence.

This document is the strategic overview and execution roadmap. It explains what we are building, why the system exists, and how implementation should progress. The source-of-truth technical architecture remains [architecture.md](architecture.md).

## Product Vision

Nexus-KB helps enterprises turn fragmented internal knowledge into searchable, reviewable, and auditable intelligence.

The system combines:

- Retrieval augmented generation for semantic search and grounded answers.
- Knowledge Graph extraction for entities, relationships, and dependency mapping.
- MCP connectors for controlled access to enterprise systems such as Confluence and legacy databases.
- RBAC and audit trails so AI workflows inherit real user permissions.
- Human review workflows for sensitive or low-confidence extraction results.
- High-availability vector search, starting with the Qdrant multi-node demo already present in this repository.

## Current Repository State

This repository is currently in foundation stage.

Implemented or present:

- Public documentation baseline.
- Agent rules and local AI workflow configuration.
- Experience Engine integration rules in `.rules`.
- Qdrant multi-node demo in `qdrant-multi-node-cluster/`.
- Architecture source-of-truth in `docs/architecture.md`.
- Phase 1 scaffold for local and Obsidian ingestion, PostgreSQL metadata schema, Qdrant wrapper, FastAPI API, and synthetic tests.

Not implemented yet:

- Full web console.
- Production API gateway.
- LLM Gateway.
- MCP connector implementations.
- Knowledge Graph builder.
- Production deployment stack.

Do not document these future components as runnable until code and verification exist.

## Architecture Pillars

### Governed Retrieval

RAG must respect source permissions. Search results and answer contexts should only include documents the requesting user is allowed to read.

### Knowledge Graph Extraction

The graph layer should model entities, relationships, document lineage, confidence, and review state. Graph writes should happen only after policy checks and review rules pass.

### MCP Connector Boundary

MCP connectors are the controlled bridge into enterprise sources. They must propagate user context, enforce least privilege, and redact sensitive protocol data from logs.

### LLM Gateway

All model access should go through a gateway responsible for routing, caching, retries, cost telemetry, prompt category tracking, and provider abstraction.

### Audit and Review

Every sensitive workflow should emit audit events. Low-confidence or high-risk extraction should pause for human review before commit.

### Open-Source Safety

The public repository must not contain customer documents, internal URLs, credentials, local sessions, model weights, vector snapshots, or private agent memory.

## Target Processing Flow

1. User or service creates an ingestion request with actor context and source metadata.
2. RBAC validates access before source content is read.
3. Rule Engine selects priority, parser strategy, review requirements, and model tier.
4. Parser worker chunks documents and extracts candidate facts.
5. Reducer merges duplicate entities and resolves conflicts.
6. Review workflow approves, edits, rejects, or requests refinement.
7. Commit writes verified results to metadata storage, vector index, and graph storage.
8. Audit records link source document, chunk IDs, model route, prompt category, confidence, reviewer, and storage IDs.

## MVP Scope

The first useful Nexus-KB milestone should avoid building the full enterprise platform at once. The MVP should prove a narrow but complete path:

- Ingest synthetic documents.
- Chunk and embed content.
- Store vectors in Qdrant.
- Store document metadata in a relational database.
- Search with permission-aware filters.
- Capture audit events for ingestion and search.
- Provide a minimal review surface for extracted candidates.

The MVP should use synthetic data only.

## Roadmap

### Phase 0: Foundation

Status: in progress.

Goals:

- Keep documentation coherent and public-safe.
- Keep `docs/action.md` as roadmap and `docs/architecture.md` as source-of-truth architecture.
- Preserve Qdrant demo as the first runnable infrastructure component.
- Keep local runtime data ignored and placeholder directories represented with `.gitkeep`.

Exit criteria:

- README points to the correct document roles.
- Qdrant demo instructions are accurate.
- No public documentation claims a full stack is runnable.

### Phase 1: Vector Ingestion MVP

Status: in progress.

Implemented:

- PostgreSQL schema for documents, chunks, and ingestion runs.
- SQLAlchemy ORM models and Alembic migration config.
- FastAPI service scaffold under `services/nexus-api`.
- Pydantic contracts under `packages/shared-contracts`.
- Qdrant wrapper under `packages/vector-client`.
- Local and Obsidian markdown parser under `workers/document-parser`.
- Frontmatter, tag, and wikilink extraction.
- Plain text and markdown only, with `file_extension` and `mime_type` stored for future parser expansion.
- Deterministic embedding provider for tests and sentence-transformers provider for runtime.
- Synthetic unit tests.
- Phase 1.5 markdown-aware chunking and reranked search with snippets.

Remaining goals:

- Add CI job wiring for the live PostgreSQL and Qdrant integration tests.
- Add richer chunking strategy after baseline behavior is proven.

Key decisions:

- Embedding provider for local development.
- Metadata database choice for MVP.
- Chunk schema and source lineage contract.

Verification:

- Unit tests for chunking.
- Integration test for Qdrant insert/search.
- Contract test for metadata persistence.

### Phase 2: Audit and Review

Goals:

- Add immutable audit event model.
- Add review queue for extracted candidates.
- Track approval, rejection, modification, reviewer, and confidence.

Key decisions:

- Audit storage schema.
- Review status lifecycle.
- Retention and redaction policy.

Verification:

- Tests for audit event creation.
- Tests for review state transitions.
- Security tests for unauthorized review access.

### Phase 3: MCP Source Connector

Goals:

- Add first MCP connector scaffold.
- Support source discovery and document read with user-context authorization.
- Keep mutating tools disabled by default.

Key decisions:

- Connector implementation language.
- Authentication propagation model.
- Tool schema format and error contract.

Verification:

- Schema tests for MCP tools.
- Authorization failure tests.
- Redaction tests for logs and errors.

### Phase 4: Knowledge Graph Builder

Goals:

- Extract entities and relationships from approved chunks.
- Merge duplicate entities.
- Store relationship confidence and provenance.
- Support graph lookup from search results.

Key decisions:

- Graph database or relational graph model.
- Entity identity strategy.
- Conflict resolution policy.

Verification:

- Unit tests for entity merge.
- Integration tests for graph writes.
- Regression tests for provenance and confidence.

### Phase 5: LLM Gateway

Goals:

- Centralize model routing.
- Add prompt category tracking.
- Add caching, retry, telemetry, and provider abstraction.
- Support local and external models without exposing provider-specific code to workers.

Key decisions:

- Cache key strategy.
- Provider adapter contract.
- Token and cost telemetry schema.

Verification:

- Tests for routing rules.
- Tests for cache hit/miss behavior.
- Tests for retry and failure handling.

## Planned Repository Structure

Future implementation should follow this shape when code is added:

```text
apps/
|-- web-console/

services/
|-- api-gateway/
|-- auth-service/
|-- rule-engine/
|-- llm-gateway/

workers/
|-- document-parser/
|-- graph-builder/

mcp-servers/
|-- confluence-bridge/
|-- internal-db-bridge/

packages/
|-- shared-contracts/
|-- audit-client/
|-- vector-client/

infrastructure/
|-- docker/
|-- migrations/
|-- observability/
```

Create these directories only when they contain real implementation or intentional placeholders.

## Decision Log

| Decision | Current Direction | Status |
| --- | --- | --- |
| Product name | Nexus-KB | Accepted |
| Repository name | Rename later | Open |
| Vector DB | Qdrant HA demo first | Accepted |
| Architecture source | `docs/architecture.md` | Accepted |
| Roadmap source | `docs/action.md` | Accepted |
| Experience memory | Local Experience Engine via `.rules` | Accepted |
| Public data policy | Synthetic samples only | Accepted |
| First connector | Confluence-oriented MCP bridge | Planned |

## Non-Goals For Now

- Do not build a full enterprise UI before the ingestion and audit contracts exist.
- Do not commit real enterprise documents, source credentials, vector snapshots, or model weights.
- Do not expose internal connector details in public examples.
- Do not claim production readiness until deployment, security, tests, and observability are implemented.
- Do not let agent-specific local runtime state become part of the public repository.

## Immediate Next Actions

1. Keep README and localized README files aligned with the Nexus-KB name.
2. Decide the Phase 1 implementation language and package layout.
3. Add `.env.example` for future service configuration once the first service exists.
4. Define the document metadata schema and chunk schema.
5. Add the first vector ingestion test against the Qdrant demo.
