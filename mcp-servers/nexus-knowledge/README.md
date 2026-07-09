# nexus-knowledge MCP server

Read-only MCP tools for AI agents connecting through an MCP Gateway:

- `search_knowledge` — search the indexed, published knowledge base.
- `ask_knowledge` — RAG answer with citations, backed by the internal LLM gateway.
- `list_documents` — list published documents visible to the caller's workspaces.

Every tool call is workspace-scoped exactly like the web console: an admin token sees
everything, a member token only sees their own workspaces (empty membership means empty
results, not everything — fail closed). No upload/write tools are exposed.

## Running

Requires the full search/RAG stack on `PYTHONPATH` (same as running `services/nexus-api`)
plus this package — see the root `README.md` section "MCP knowledge server".

```powershell
$env:PYTHONPATH="packages/shared-contracts;packages/vector-client;workers/document-parser;workers/graph-builder;services/nexus-api;services/llm-gateway;mcp-servers/confluence-bridge;mcp-servers/nexus-knowledge"
'{"tool":"search_knowledge","token":"<jwt>","arguments":{"query":"onboarding checklist"}}' | python -m nexus_knowledge_mcp
```

Get a token the same way the web console does, via `POST /api/v1/auth/dev-token`
(dev mode) — see `services/nexus-api/nexus_api/routers/auth.py`.

## Token verification

`InternalJwtVerifier` verifies the same internal HS256 JWT nexus-api issues (shared
`JWT_SECRET`). This is an interim choice: the target design has the MCP Gateway issue
Keycloak-signed (RS256) tokens verified via that realm's JWKS endpoint. Swapping verifiers
is a one-class change — `NexusKnowledgeBridge` only depends on the `TokenVerifier` protocol
in `auth.py`, not on how a token gets verified.

## Architecture note

This package does not duplicate search/RAG logic. `wiring.py` constructs the bridge from the
*same* `SearchService` / `RagService` classes `services/nexus-api` uses for its REST API, so
an agent can never see more (or less) than a logged-in user would.
