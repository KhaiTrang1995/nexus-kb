# MCP Tool Domain Map

The MCP implementation is planned, not currently present. Use this map when adding connector modules.

- `source-discovery`: list readable spaces, folders, databases, or repositories for the current user.
- `document-read`: fetch document metadata and content after authorization checks.
- `document-search`: query source systems without bypassing source permissions.
- `schema-introspection`: inspect legacy database schemas without exposing data rows by default.
- `maintenance`: health checks, connector diagnostics, and cache refresh operations.
- `admin`: restricted operations requiring explicit configuration and audit.

Every tool must define input schema, output schema, authorization behavior, audit events, and redaction rules.
