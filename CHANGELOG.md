# Changelog

All notable changes to Nexus-KB are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project aims to follow semantic versioning once it leaves the reference-implementation stage. Until then, dated entries track meaningful documentation and implementation changes.

## [Unreleased]

### Added

- `docs/action.md`: strategy, roadmap, and execution plan. This document was referenced by `README.md`, `README-VN.md`, `README-CN.md`, `CONTRIBUTING.md`, and `docs/phase-checklist.md` but did not exist, leaving broken links across the repository.
- `docs/architecture.md`: an Implementation Status section that maps each architecture layer to the module that implements it, plus a Related Documents pointer to the roadmap and phase checklist.
- This `CHANGELOG.md`.

### Changed

- `docs/architecture.md`: replaced the aspirational "Planned Monorepo Structure" with a "Monorepo Structure" section that separates implemented modules (`services/nexus-api`, `services/llm-gateway`, `workers/document-parser`, `workers/graph-builder`, `mcp-servers/confluence-bridge`, `packages/shared-contracts`, `packages/vector-client`, `infrastructure/alembic`) from planned ones, removing architecture drift.
- `README.md`: added a Changelog reference so notable changes are discoverable.

### Fixed

- Repository-wide broken links to `docs/action.md`.

## Phase History

The detailed, test-gated phase history is tracked in [docs/phase-checklist.md](docs/phase-checklist.md) and summarized in [docs/action.md](docs/action.md). Delivered phases at the time this changelog was created:

- Phase 0: Foundation, documentation, agent rules, and repository safety baseline.
- Phase 1 / 1.5: Local and Obsidian ingestion, PostgreSQL metadata, Qdrant vectors, hybrid reranking.
- Phase 2: Audit logs, review queue, review actions, and mock reviewer RBAC.
- Phase 3: Confluence-oriented MCP source connector scaffold.
- Phase 4: Knowledge Graph builder, relational graph tables, graph APIs, and search graph context.
- Phase 5: LLM Gateway slice with routing, caching, retry, telemetry, and provider abstraction.
