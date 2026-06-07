# Nexus-KB

Nexus-KB is an open-source reference architecture for an Enterprise RAG and Knowledge Graph Engine, covering MCP connectors, governed AI workflows, and high-availability vector search.

当前仓库处于架构和基础设施阶段。可运行的示例位于 `qdrant-multi-node-cluster/`，用于启动多节点 Qdrant 集群并验证向量数据库行为。

## Goals

- Define a clear architecture for document ingestion, semantic search, knowledge graph extraction, audit, and human review.
- Keep AI-agent rules explicit so generated code follows predictable security, testing, and architecture standards.
- Provide a reusable Qdrant high-availability demo for local validation.
- Maintain open-source hygiene by avoiding committed secrets, runtime logs, local sessions, raw documents, and generated cache data.

## Main Documents

- [README.md](README.md): main project overview.
- [docs/action.md](docs/action.md): Nexus-KB strategy, roadmap, and execution plan.
- [docs/architecture.md](docs/architecture.md): source-of-truth architecture.
- [AGENTS.md](AGENTS.md): AI agent and contributor rules.
- [CONTRIBUTING.md](CONTRIBUTING.md): contribution guide.
- [SECURITY.md](SECURITY.md): vulnerability reporting policy.
- [qdrant-multi-node-cluster/README.md](qdrant-multi-node-cluster/README.md): Qdrant demo guide.

## Repository Rules

- Do not commit credentials, tokens, logs, sessions, customer data, raw documents, model weights, or database snapshots.
- Use `.gitkeep` only for intentional placeholder directories.
- Keep architecture changes synchronized with `docs/architecture.md`.
