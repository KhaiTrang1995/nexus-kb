# Confluence Bridge MCP Connector

This directory contains the Phase 3 source connector scaffold for Nexus-KB.

The connector is intentionally transport-neutral: `ConfluenceBridge` exposes typed tool definitions and structured tool-call results that can be wrapped by an MCP runtime later. The current implementation uses an in-memory synthetic client for public-safe local verification.

## Tools

- `confluence.discover_sources`: lists readable pages in an authorized Confluence space.
- `confluence.read_document`: reads one authorized page and returns content plus a SHA-256 content hash.

Mutating `confluence.*` tools are denied by default.

## Security Model

Every call requires an `actor` object with:

- `user_id`
- `roles`, including `SourceReader`
- `allowed_spaces`, including the requested page space
- optional `source_principal`
- optional `correlation_id`

The connector fails closed for authorization checks and redacts URLs, token-like values, and email addresses from structured connector errors.

## Local Verification

```powershell
python -m pytest tests/test_mcp_confluence_bridge.py -q
```

Example JSON runner:

```powershell
$env:PYTHONPATH="mcp-servers/confluence-bridge"
'{"tool":"confluence.discover_sources","arguments":{"actor":{"user_id":"alice","roles":["SourceReader"],"allowed_spaces":["KB"],"correlation_id":"demo"},"space_key":"KB"}}' | python -m nexus_confluence_bridge
```
