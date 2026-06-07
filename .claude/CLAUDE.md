# Claude Code Project Guide

## Project Context

Enterprise Knowledge Hub is an open-source architecture workspace for an enterprise RAG and Knowledge Graph platform. The runnable implementation currently lives in `qdrant-multi-node-cluster/`.

Read these files before making substantial changes:

- `README.md`
- `docs/architecture.md`
- `AGENTS.md`

## Repository Areas

- Root and `docs/`: documentation, architecture, and governance.
- `.claude/`, `.codex/`, `.agents/`, `.hermes/`: AI-agent configuration and local automation.
- `qdrant-multi-node-cluster/`: Python and Docker Qdrant demo.

## Commands

Documentation-only changes require manual link and heading review.

Qdrant demo verification:

```bash
cd qdrant-multi-node-cluster
make test
```

Alternative:

```bash
cd qdrant-multi-node-cluster
python -m unittest discover -s tests
```

## Rules

- Follow `.claude/rules/` for code style, API conventions, and testing.
- Do not commit secrets, local sessions, raw documents, model files, vector snapshots, or logs.
- Keep architecture changes synchronized with `docs/architecture.md`.
- Keep local overrides in `CLAUDE.local.md`; this file is ignored by the root `.gitignore`.
