from __future__ import annotations

from uuid import UUID

from nexus_shared.contracts import AuditStatus, DocumentAckResponse


class AckService:
    """Second review tier: the uploader confirms they've read a newly indexed
    document before it becomes visible to anyone else in the workspace.

    Distinct from ReviewService (low-confidence chunk approval, Phase 2) --
    that gate gets a chunk into Qdrant at all; this gate flips a chunk's
    `published` payload flag so it starts showing up in search.
    """

    def __init__(self, repository, vector_client) -> None:
        self.repository = repository
        self.vector_client = vector_client

    def ack(self, document_id: UUID, actor_id: str) -> DocumentAckResponse:
        document, chunk_ids = self.repository.ack_document(document_id, actor_id)
        self.vector_client.set_payload(chunk_ids, {"published": True})
        self.repository.record_audit_log(
            actor_id=actor_id,
            action="DOCUMENT_ACK",
            status=AuditStatus.SUCCESS,
            resource_id=document_id,
            details={"chunk_count": len(chunk_ids)},
        )
        return DocumentAckResponse(document_id=document.id, acked_by=actor_id, acked_at=document.acked_at)
