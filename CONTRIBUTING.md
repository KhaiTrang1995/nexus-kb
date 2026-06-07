# Contributing

Thank you for considering a contribution to Enterprise Knowledge Hub.

## Before You Start

- Read [README.md](README.md), [docs/architecture.md](docs/architecture.md), and [AGENTS.md](AGENTS.md).
- Keep changes small and focused.
- Do not commit secrets, runtime logs, local sessions, generated cache, raw documents, model weights, or database data.

## Contribution Types

Good first contributions include:

- Improving architecture documentation.
- Adding tests or verification commands for the Qdrant demo.
- Hardening security guidance.
- Clarifying AI-agent rules.
- Adding implementation modules that follow the documented architecture.

## Development Workflow

1. Create a feature branch.
2. Make the smallest coherent change.
3. Update documentation when behavior, architecture, or commands change.
4. Run the relevant verification:
   - Documentation-only changes: check links and headings manually.
   - Qdrant demo changes:
     ```bash
     cd qdrant-multi-node-cluster
     make test
     ```
5. Open a pull request with a concise summary, verification results, and any known limitations.

## Pull Request Standard

Each pull request should include:

- What changed.
- Why it changed.
- How it was verified.
- Any follow-up work or risk.

## Style

- Prefer clear prose over broad claims.
- Keep architecture terms consistent.
- Avoid examples that expose internal systems or private data.
- Keep generated artifacts out of source control.
