# Contributing to Nexus-KB

Thank you for considering a contribution to Nexus-KB.

Nexus-KB is a public-safe reference implementation for governed RAG, audit and review workflows, MCP source connectors, Knowledge Graph construction, Qdrant vector search, and LLM Gateway routing. Keep contributions scoped, reproducible, and aligned with the current phase checklist.

## Before You Start

- Read [README.md](README.md), [AGENTS.md](AGENTS.md), [docs/architecture.md](docs/architecture.md), [docs/action.md](docs/action.md), and [docs/phase-checklist.md](docs/phase-checklist.md).
- Check the target area before editing:
  - `docs/`: architecture, roadmap, phase plans, and contributor guidance.
  - `services/nexus-api/`: FastAPI ingest, search, audit, review, and graph APIs.
  - `services/llm-gateway/`: LLM routing, cache, retry, provider abstraction, and telemetry slice.
  - `workers/document-parser/`: parsing, chunking, embedding, ingestion, audit/review routing.
  - `workers/graph-builder/`: entity extraction, relationship construction, graph persistence and lookup.
  - `mcp-servers/confluence-bridge/`: MCP source connector scaffold and authorization boundary.
  - `packages/`: shared contracts and client wrappers.
  - `qdrant-multi-node-cluster/`: standalone HA Qdrant demo.
- Do not commit secrets, API keys, internal hostnames, customer data, runtime logs, local sessions, raw documents, model weights, vector snapshots, audit exports, or database dumps.
- Use synthetic data in examples and tests.

## Contribution Types

Good contributions include:

- Improving documentation accuracy and phase checklist coverage.
- Adding tests for ingestion, search, audit, review, MCP connector, graph builder, or LLM Gateway behavior.
- Tightening RBAC, audit, redaction, or review workflow behavior.
- Extending shared contracts when API or worker behavior changes.
- Adding implementation modules that preserve the boundaries in [docs/architecture.md](docs/architecture.md).
- Improving the standalone Qdrant demo, when the change is actually scoped to `qdrant-multi-node-cluster/`.

## Development Workflow

1. Create a feature branch.
2. Inspect existing patterns in the target module.
3. Make the smallest coherent change that satisfies the issue or phase checklist item.
4. Update tests when behavior changes.
5. Update documentation when commands, APIs, architecture, or phase status changes.
6. Run the relevant verification commands.
7. Open a pull request with a concise summary, verification output, and known limitations.

## Verification

Default offline verification:

```bash
python -m pytest -q
```

Live verification, when Docker services are available:

```powershell
$env:NEXUS_KB_RUN_LIVE_TESTS="1"
$env:POSTGRES_DSN="postgresql://nexus:nexus_dev_password@localhost:5432/nexus_kb"
python -m pytest tests/test_live_integration_scaffold.py tests/test_live_graph_repository.py -q
```

Area-specific checks:

- Documentation-only changes: manually check links, headings, and consistency with `docs/architecture.md`.
- Phase changes: use [docs/phase-checklist.md](docs/phase-checklist.md) and run the tests listed for that phase.
- API changes: run affected API/service tests and ensure shared contracts stay compatible.
- Migration changes: run `alembic -c infrastructure/alembic.ini upgrade head` against a local database when possible.
- MCP connector changes:
  ```bash
  python -m pytest tests/test_mcp_confluence_bridge.py -q
  ```
- Graph builder changes:
  ```bash
  python -m pytest tests/test_graph_builder.py tests/test_graph_api.py tests/test_search_service.py -q
  ```
- LLM Gateway changes:
  ```bash
  python -m pytest tests/test_llm_gateway.py -q
  ```
- Qdrant demo-only changes:
  ```bash
  cd qdrant-multi-node-cluster
  make test
  ```

## Pull Request Standard

Each pull request should include:

- What changed.
- Why it changed.
- How it was verified, including exact commands.
- Any migration, compatibility, or operational notes.
- Follow-up work or residual risk.

## Style and Safety

- Be direct and technical.
- Prefer concrete behavior over marketing claims.
- Use consistent terms: RAG, Knowledge Graph, MCP, RBAC, audit, queue, worker, vector database.
- Keep examples public-safe and synthetic.
- Keep generated artifacts and local runtime state out of source control.
- Do not claim production readiness unless deployment, security, observability, and operational controls are actually implemented and verified.
