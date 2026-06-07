# API Conventions

These conventions apply when API services are added to the repository.

## REST Design

- Use versioned paths such as `/api/v1/documents`.
- Use plural resource names.
- Use standard HTTP methods:
  - `GET` for reads.
  - `POST` for creation or command-style actions.
  - `PUT` for full replacement.
  - `PATCH` for partial updates.
  - `DELETE` for deletion.

## Request and Response

- Use JSON for public API contracts.
- Validate inputs at the boundary.
- Include correlation IDs in logs and audit events.
- Do not return raw stack traces or secret values.

Example success response:

```json
{
  "data": {},
  "meta": {
    "request_id": "req_123"
  }
}
```

Example error response:

```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "The request is invalid",
    "details": []
  },
  "meta": {
    "request_id": "req_123"
  }
}
```

## Authorization and Audit

- Check authorization before reading source documents or graph data.
- Emit audit events for ingestion, review, approval, rejection, and commit operations.
- Fail closed when the authorization decision is unavailable.
