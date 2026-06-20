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
=======
# Action Plan: Strategy, Roadmap, and Execution

This document is the strategy, roadmap, and execution plan for Nexus-KB. Read it with [architecture.md](architecture.md) (source-of-truth architecture) and [phase-checklist.md](phase-checklist.md) (phase completion gates). Architecture decisions live in `architecture.md`; sequencing and intent live here.

Nexus-KB is the implementation name for the Enterprise Knowledge Hub reference architecture. This repository is a local reference implementation, not a production-ready enterprise stack. All examples and tests use synthetic data.

## Vision

Make fragmented enterprise knowledge searchable, reviewable, auditable, and graph-aware without giving up governance. The platform should let an organization ingest documents, retrieve them with semantic and lexical signals, extract entities and relationships, and keep every sensitive action behind authorization, human review, and an immutable audit trail.

## Strategic Principles

- Build local-first, then promote to production through reproducible infrastructure.
- Treat authorization and audit as mandatory platform concerns, not optional add-ons.
- Keep source connectors, AI processing, storage, and review workflows separated by explicit service boundaries.
- Route all model access through a gateway that centralizes routing, caching, retries, cost controls, and observability.
- Keep raw documents, model files, vector snapshots, and runtime logs out of git.
- Do not claim production readiness or capabilities that are not backed by code and tests.

## Roadmap

The roadmap is phase-based. Each phase has a defined intent and a completion gate in [phase-checklist.md](phase-checklist.md). Do not call a phase complete unless its checklist tests pass.

### Delivered phases

| Phase | Intent | Primary code surface |
| --- | --- | --- |
| Phase 0: Foundation | Documentation, source-of-truth architecture, agent rules, repository safety baseline. | `README.md`, `docs/`, `AGENTS.md`, `.rules`, `.claude/rules/` |
| Phase 1 / 1.5: Vector Ingestion MVP | Local and Obsidian markdown ingestion, content-hash dedup, markdown-aware chunking, embeddings, PostgreSQL metadata, Qdrant search, hybrid reranking. | `workers/document-parser`, `packages/vector-client`, `services/nexus-api` |
| Phase 2: Audit and Review | Immutable audit events, review queue, approve/reject/modify actions, mock reviewer RBAC, low-confidence routing. | `services/nexus-api/nexus_api/audit.py`, `review.py` |
| Phase 3: MCP Source Connector | Confluence-oriented connector scaffold with source discovery, document read, user-context authorization, disabled mutating tools, redacted errors. | `mcp-servers/confluence-bridge` |
| Phase 4: Knowledge Graph Builder | Entity and relationship extraction from approved chunks, duplicate merge, confidence and provenance, relational graph tables, graph APIs, search graph context. | `workers/graph-builder`, graph APIs in `services/nexus-api` |
| Phase 5: LLM Gateway | Provider abstraction with task routing, prompt-category tracking, deterministic test provider, retry policy, cache keys, telemetry without raw prompt content. | `services/llm-gateway` |

### Planned phases

These phases are not implemented. They are recorded here so future work stays aligned with the architecture and does not drift.

| Phase | Intent | Primary dependencies |
| --- | --- | --- |
| Phase 6: Real LLM-Assisted Extraction | Route graph entity and relationship extraction through the LLM Gateway instead of metadata and heuristic fallbacks. Keep deterministic providers for offline tests. | Phase 4, Phase 5 |
| Phase 7: Production AuthN/AuthZ | Replace mock `X-User-Role` headers with real identity, RBAC policy service, and least-privilege enforcement across API, review, and connector surfaces. | Phase 2, Phase 3 |
| Phase 8: Web Console | Operational UI for search, graph exploration, ingestion status, and review approval. Compact operational interface, not a marketing landing page. | Phase 1-4, Phase 7 |
| Phase 9: Orchestration and Job Queue | Move long-running ingestion and graph builds onto a durable queue with correlation IDs, actor context, and policy decisions carried per job. | Phase 1, Phase 4 |
| Phase 10: Additional MCP Connectors | Add further controlled source connectors beyond Confluence using the established authorization, redaction, and tool-guarding pattern. | Phase 3, Phase 7 |
| Phase 11: Deployment Hardening and Observability | Isolated networks, secret management, TLS, backup policy, metrics, dashboards, and alerts for storage and queue components. | All prior phases |

The phase numbering for planned work is indicative. Reprioritize against business need, but keep each item behind its architectural dependencies.

## Execution Discipline

For any change to architecture, storage, RBAC, audit, MCP, or LLM surfaces:

1. Read `AGENTS.md`, `README.md`, `docs/architecture.md`, and `docs/phase-checklist.md` first.
2. Consult the local Experience Engine described in `.rules` when available; if it is unavailable, continue and note that it failed open.
3. Keep backend business logic decoupled from FastAPI and infrastructure clients through ports and adapters.
4. Update shared contracts, API wiring, migrations, tests, and index documentation together.
5. Verify with the phase checklist tests before claiming completion. Cite the tests that prove each item.
6. Record notable changes in [../CHANGELOG.md](../CHANGELOG.md) and keep architecture changes synchronized with `docs/architecture.md`.

## Definition of Done per Phase

A phase is done when:

- The checklist intent in `phase-checklist.md` is implemented behind clean module boundaries.
- The listed offline tests pass without Docker or external APIs.
- Live tests, when applicable, pass behind the `NEXUS_KB_RUN_LIVE_TESTS` gate.
- No regression listed in the phase checklist is reintroduced.
- Documentation, contracts, and tests are updated in the same change.

## Out of Scope for the Current Reference Implementation

- Production authentication and full RBAC enforcement.
- Production API gateway and web console.
- Real enterprise connector adapters beyond the Confluence scaffold.
- PDF, DOCX, image, and OCR ingestion.
- Deployment hardening and production observability.

These remain future work and must not be presented as delivered.
