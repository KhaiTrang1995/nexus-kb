---
name: repo-onboarding
description: Understand this repository quickly before making changes. Use for architecture discovery, ownership mapping, command selection, and initial implementation planning.
---

# Repo Onboarding Skill

## Workflow
- Read `AGENTS.md`, `README.md`, and `docs/architecture.md`.
- Determine target area: root docs, agent configuration, Hermes runtime template, or `qdrant-multi-node-cluster/`.
- Identify the minimal file set needed for the task.
- Select verification commands before editing.

## Verification defaults
- Documentation: manual link, heading, and source-of-truth consistency check.
- Qdrant demo: `cd qdrant-multi-node-cluster && make test`.
- Agent configuration: verify referenced files exist and local-only artifacts remain ignored.

## References
- `references/module-map.md`
- `references/verification-map.md`
