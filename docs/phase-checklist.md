# Phase Checklist and Agent Handoff Notes

This document is the operating checklist for agents continuing Nexus-KB implementation. Use it with [architecture.md](architecture.md), [action.md](action.md), [../README.md](../README.md), and [../AGENTS.md](../AGENTS.md).

The goal is to prevent phase drift: do not call a phase complete unless the code, contracts, migrations, APIs, and tests listed here prove it.

## Current Phase State

| Phase | Status | Main code surface | Verification evidence |
| --- | --- | --- | --- |
| Phase 0: Foundation | Implemented baseline | `README.md`, `docs/architecture.md`, `docs/action.md`, `AGENTS.md`, `.rules` | Documentation links and safety rules are present. |
| Phase 1 / 1.5: Vector Ingestion MVP | Implemented local MVP | `workers/document-parser`, `packages/vector-client`, `services/nexus-api`, `infrastructure/alembic/versions/001_phase1_schema.py` | Offline tests for parsing, chunking, ingestion, search; live scaffold for Postgres/Qdrant. |
| Phase 2: Audit and Review | Implemented local MVP | `services/nexus-api/nexus_api/audit.py`, `review.py`, `workers/document-parser/...`, migration `002_add_audit_and_review_tables.py` | `tests/test_audit_trail.py`, `tests/test_review_flow.py`, `tests/test_rbac_review.py`. |
| Phase 3: MCP Source Connector | Implemented scaffold | `mcp-servers/confluence-bridge` | `tests/test_mcp_confluence_bridge.py`; JSON runner via `python -m nexus_confluence_bridge`. |
| Phase 4: Knowledge Graph Builder | Implemented local MVP | `workers/graph-builder`, graph APIs in `services/nexus-api`, migration `003_add_graph_tables.py` | `tests/test_graph_builder.py`, `tests/test_graph_api.py`, graph search tests, `tests/test_live_graph_repository.py`. |
| Phase 5: LLM Gateway | Implemented slice | `services/llm-gateway` | `tests/test_llm_gateway.py`. |

## Global Rules for Future Agents

- Read `AGENTS.md`, `README.md`, `docs/architecture.md`, and this file before changing implementation structure.
- Treat `docs/architecture.md` as source-of-truth architecture and `docs/action.md` as roadmap context.
- Before writing code for architecture, storage, RBAC, audit, MCP, or LLM surfaces, call the Experience Engine described in `.rules`. If it is unavailable, continue and note that it failed open.
- Do not commit secrets, real enterprise documents, raw logs, vector snapshots, model files, audit exports, local sessions, or private agent memory.
- Keep raw data and runtime state out of git. `.hermes/`, `data/`, `datasets/`, `models/`, and `secrets/` are local-sensitive areas.
- Keep changes scoped. Do not rewrite generated runtime files or unrelated untracked files.
- Use synthetic examples only.
- Do not claim production readiness. Current status is a local reference implementation.
- Do not bypass RBAC, audit logging, review queue behavior, or graph provenance checks to make tests pass.

## Phase 1 / 1.5 Checklist

Implemented intent:

- Local and Obsidian markdown ingestion.
- Frontmatter, tags, wikilinks, mime type, file extension, title, content hash.
- Markdown-aware chunking with section paths.
- Deterministic embedding provider for tests and sentence-transformer provider for runtime.
- PostgreSQL metadata tables: `documents`, `chunks`, `ingestion_runs`.
- Qdrant vector wrapper and search integration.
- Hybrid reranking with lexical/title/tag/heading signals and snippets.

Do not call Phase 1 stable if any of these fail:

- `python -m pytest tests/test_chunker_embedding.py tests/test_ingestion_pipeline.py tests/test_search_service.py -q`
- Ingestion still writes changed docs and skips unchanged docs.
- Search still joins Qdrant payload IDs with PostgreSQL chunk/document metadata.
- README/API `PYTHONPATH` includes `packages/shared-contracts`, `packages/vector-client`, `workers/document-parser`, `workers/graph-builder`, and `services/nexus-api`.

Known pitfalls:

- Live tests use `psycopg.connect`, so live `POSTGRES_DSN` must be `postgresql://...`, not `postgresql+psycopg://...`.
- Runtime SQLAlchemy config can use `postgresql+psycopg://...`.
- Existing Compose databases may need `alembic stamp 001_phase1_schema` before `upgrade head` if initialized from SQL scripts before Alembic versioning.

## Phase 2 Checklist

Implemented intent:

- `audit_logs` immutable event table.
- `review_items` queue table.
- Audit event contracts and review action contracts.
- Ingestion audit events:
  - `INGEST_START`
  - `DOCUMENT_READ`
  - `CHUNK_GENERATED`
  - `INGEST_FINISH`
- Search audit event:
  - `SEARCH_QUERY`
- Review audit event:
  - `ITEM_REVIEW`
- Low-confidence chunks route to `review_items` and skip Qdrant until approved or modified.
- Review actions support `APPROVE`, `REJECT`, and `MODIFY`.
- Mock reviewer RBAC uses `X-User-Role: Reviewer`.

Required tests:

- `python -m pytest tests/test_audit_trail.py tests/test_review_flow.py tests/test_rbac_review.py -q`

Do not regress:

- Audit details must not include raw document content.
- Non-reviewer roles must receive `403` on review queue/action routes.
- Review items cannot be finalized twice.
- Approved or modified review items must upsert to Qdrant.
- Rejected items must not be indexed.

## Phase 3 Checklist

Implemented intent:

- First MCP connector scaffold: `mcp-servers/confluence-bridge`.
- Tools:
  - `confluence.discover_sources`
  - `confluence.read_document`
- Actor context:
  - `user_id`
  - `roles`
  - `allowed_spaces`
  - optional `source_principal`
  - optional `correlation_id`
- Read authorization requires role `SourceReader` and requested page space in `allowed_spaces`.
- Mutating `confluence.*` tools are disabled by default.
- Tool calls have structured `ToolCallResult`.
- Connector errors redact URLs, token-like values, and email addresses.
- JSON runner exists via `python -m nexus_confluence_bridge`.

Required tests:

- `python -m pytest tests/test_mcp_confluence_bridge.py -q`

Manual runner check:

```powershell
$env:PYTHONPATH="mcp-servers/confluence-bridge"
'{"tool":"confluence.discover_sources","arguments":{"actor":{"user_id":"alice","roles":["SourceReader"],"allowed_spaces":["KB"],"correlation_id":"demo"},"space_key":"KB"}}' | python -m nexus_confluence_bridge
```

Do not regress:

- Do not add mutating tools unless explicitly approved and guarded.
- Do not log credentials or internal source URLs in errors.
- Keep connector transport-neutral unless adding a real MCP runtime wrapper with tests.

## Phase 4 Checklist

Implemented intent:

- `graph_entities` and `graph_relationships` tables via migration `003_add_graph_tables.py`.
- Shared graph contracts:
  - `GraphChunkInput`
  - `GraphEntityCandidate`
  - `GraphRelationshipCandidate`
  - `GraphEntityRecord`
  - `GraphRelationshipRecord`
  - `GraphBuildResult`
- Metadata extractor reads explicit metadata entities/relationships and has a simple content fallback.
- Duplicate entity merge uses normalized name and entity type.
- Relationship records store confidence and provenance.
- `GraphBuildService` builds from `list_approved_graph_chunks`.
- Metadata repository excludes pending/rejected review chunks from graph build.
- API endpoints:
  - `POST /api/v1/graph/build`
  - `GET /api/v1/graph/chunks/{chunk_id}`
- Search results include `graph_entities` and `graph_relationships` when graph context exists.

Required tests:

- `python -m pytest tests/test_graph_builder.py tests/test_graph_api.py tests/test_search_service.py -q`
- Live Postgres graph coverage when available:

```powershell
$env:NEXUS_KB_RUN_LIVE_TESTS="1"
$env:POSTGRES_DSN="postgresql://nexus:nexus_dev_password@localhost:5432/nexus_kb"
python -m pytest tests/test_live_graph_repository.py -q
```

Do not regress:

- Graph writes must only come from approved/direct-commit chunks.
- Pending or rejected review items must not feed graph build.
- Provenance must preserve `chunk_id` and `document_id`.
- Search must still work when no graph repository is provided.

## Phase 5 Checklist

Implemented intent:

- `services/llm-gateway` includes provider abstraction.
- Gateway supports:
  - task routing
  - prompt category tracking
  - deterministic test provider
  - retry policy
  - cache key construction
  - telemetry records
- Failure telemetry must not include raw prompt content.

Required tests:

- `python -m pytest tests/test_llm_gateway.py -q`

Do not regress:

- Workers must not call model providers directly once they integrate LLM behavior; route through the gateway.
- Do not store raw prompts, secrets, API keys, or provider-specific credentials in telemetry.
- External providers must be optional and disabled in offline tests.

## Repository-Wide Verification

Default offline verification:

```powershell
python -m pytest -q
```

Current expected offline result at the time this checklist was written:

```text
36 passed, 4 skipped, 1 warning
```

Live verification, when Docker services and Qdrant are available:

```powershell
$env:NEXUS_KB_RUN_LIVE_TESTS="1"
$env:POSTGRES_DSN="postgresql://nexus:nexus_dev_password@localhost:5432/nexus_kb"
python -m pytest tests/test_live_integration_scaffold.py tests/test_live_graph_repository.py -q
```

Known live warning:

- Local Qdrant may be newer than pinned `qdrant-client==1.13.3`. The tests can still pass with a version mismatch warning, but do not ignore functional failures.

## Handoff Notes for Agents

- Check `git status --short` before editing. This repo may contain unrelated untracked/local files.
- Prefer `rg` when available; PowerShell environments may not have it, so use `Get-ChildItem` and `Select-String` when needed.
- Use `apply_patch` for hand edits.
- Do not delete or clean local `.hermes/`, `data/`, `datasets/`, `models/`, `secrets/`, `.venv/`, or generated runtime files unless explicitly asked.
- When adding new routes, update contracts, API wiring, tests, and README/index docs together.
- When adding a migration, verify:
  - model imports under Alembic env
  - `alembic upgrade head`
  - live tests if the schema affects runtime behavior
- When adding a new package path, update `tests/_paths.py` and README `PYTHONPATH`.
- When marking a phase complete, cite tests that prove every checklist item, not just broad green status.
