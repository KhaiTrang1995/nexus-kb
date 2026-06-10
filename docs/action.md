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
