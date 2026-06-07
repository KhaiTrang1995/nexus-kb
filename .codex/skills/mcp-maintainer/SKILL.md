---
name: mcp-maintainer
description: Operate and maintain the local MCP server for this repository. Use for MCP tool updates, policy-guard changes, host configuration, and MCP runtime troubleshooting.
---

# MCP Maintainer Skill

## Workflow
- Read `docs/architecture.md` and confirm the MCP connector boundary being changed.
- If an MCP implementation exists, inspect the affected connector modules and policy guards before editing.
- If no MCP implementation exists yet, update architecture, contracts, or scaffolding without inventing runnable commands.
- Validate with project scripts only when they exist; otherwise perform manual contract and safety review.

## Safety rules
- Enforce least-privilege source access and user-context propagation.
- Keep mutating and destructive tools behind explicit flags and confirmation tokens.
- Do not log protocol payloads, credentials, document content, or internal hostnames.
- Fail closed when authorization or policy checks are unavailable.

## References
- `references/tool-domain-map.md`
- `references/operations-runbook.md`
