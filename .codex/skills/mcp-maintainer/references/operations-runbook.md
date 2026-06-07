# MCP Operations Runbook

## Current State

Enterprise Knowledge Hub documents the MCP connector layer in `docs/architecture.md`. A runnable MCP server is not present in this repository yet.

## Required Controls

- Propagate the requesting user's authorization context to every source connector.
- Enforce least-privilege access at the connector boundary.
- Keep mutating tools disabled by default.
- Require explicit confirmation tokens for destructive maintenance operations.
- Redact credentials, document content, protocol payloads, and internal hostnames from logs.

## Verification

- If implementation scripts exist, run the relevant typecheck, build, and test commands documented with that implementation.
- If scripts do not exist, verify contracts manually and update documentation so future contributors know the expected command.
- Confirm `.gitignore` excludes local credentials, sessions, logs, and generated runtime data.
