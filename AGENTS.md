# Repository Agent Guide

This file defines the operating baseline for AI coding agents and human contributors working in this repository.

## Scope

The repository contains:

- Architecture documentation for Enterprise Knowledge Hub.
- Project-scoped agent configuration under `.codex/`, `.claude/`, `.agents/`, and `.hermes/`.
- A runnable Qdrant multi-node demo under `qdrant-multi-node-cluster/`.

## Required Workflow

1. Read `README.md`, `docs/architecture.md`, and `docs/phase-checklist.md` before changing architecture, rules, or implementation structure.
2. Check the target area before editing:
   - Root and `docs/`: project documentation and governance.
   - `.codex/`, `.claude/`, `.agents/`, `.hermes/`: agent configuration and local automation.
   - `qdrant-multi-node-cluster/`: runnable Python and Docker demo.
3. Keep changes scoped. Do not rewrite unrelated generated files, local runtime state, or private configuration.
4. Prefer explicit, reproducible commands. Do not rely on undocumented local state.
5. Before writing code, inspect existing patterns and update tests or verification steps when behavior changes.

## Architecture Rules

- Treat `docs/architecture.md` as the source of truth.
- Use clean boundaries between UI, backend services, workers, MCP connectors, and storage.
- Do not bypass RBAC, audit logging, or human review in workflows that process sensitive documents.
- Keep LLM calls behind a gateway that supports model routing, caching, retries, and observability.
- Keep raw documents, model files, vector snapshots, and audit exports out of git.

## Security Rules

- Never commit credentials, API keys, internal hostnames, customer data, logs, local sessions, or agent memory.
- Use `.env.example` for required configuration keys and document expected values without secrets.
- Prefer least-privilege access for MCP connectors and storage clients.
- Fail closed for authorization checks and document access checks.

## Verification Guidance

- Documentation changes: review links and headings manually.
- Qdrant demo changes: run tests from `qdrant-multi-node-cluster/` with `make test` or `python -m unittest discover -s tests`.
- Agent configuration changes: verify that referenced files exist and local-only files remain ignored.
- Phase changes: use `docs/phase-checklist.md` as the completion checklist and do not mark a phase complete without the listed tests or equivalent evidence.

## Writing Standards

- Be direct and technical.
- Avoid marketing claims that are not backed by implementation or documentation.
- Use consistent terminology: RAG, Knowledge Graph, MCP, RBAC, audit, queue, worker, vector database.
- Keep examples public-safe and free of company-private data.
