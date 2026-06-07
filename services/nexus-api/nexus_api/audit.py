from __future__ import annotations

from nexus_shared.contracts import AuditRecord


def list_audit_records(
    repository,
    limit: int = 50,
    offset: int = 0,
    action_filter: str | None = None,
    actor_filter: str | None = None,
) -> list[AuditRecord]:
    limit = min(max(limit, 1), 200)
    offset = max(offset, 0)
    return repository.list_audit_logs(
        limit=limit,
        offset=offset,
        action_filter=action_filter,
        actor_filter=actor_filter,
    )
