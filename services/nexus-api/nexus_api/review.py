from __future__ import annotations

from uuid import UUID

from fastapi import HTTPException

from nexus_document_parser.embedding import EmbeddingProvider
from nexus_shared.contracts import (
    AuditStatus,
    QdrantChunkPayload,
    ReviewAction,
    ReviewActionRequest,
    ReviewActionResponse,
    ReviewItemRecord,
    ReviewStatus,
)


REVIEWER_ROLE = "Reviewer"
AUDITOR_ROLE = "Auditor"
PRIVILEGED_ROLES = frozenset({REVIEWER_ROLE, AUDITOR_ROLE})


def require_reviewer(role: str | None) -> None:
    """Require Reviewer or Auditor — matches web console role model."""
    if role not in PRIVILEGED_ROLES:
        raise HTTPException(status_code=403, detail="reviewer role required")


class ReviewService:
    def __init__(self, repository, vector_client, embedding_provider: EmbeddingProvider) -> None:
        self.repository = repository
        self.vector_client = vector_client
        self.embedding_provider = embedding_provider

    def list_queue(self, limit: int = 50, offset: int = 0, min_confidence: float | None = None) -> list[ReviewItemRecord]:
        return self.repository.list_review_items(
            limit=min(max(limit, 1), 200),
            offset=max(offset, 0),
            min_confidence=min_confidence,
            status=ReviewStatus.PENDING,
        )

    def apply_action(self, request: ReviewActionRequest, reviewer_id: str) -> ReviewActionResponse:
        item = self.repository.get_review_item(request.item_id)
        if item is None:
            raise HTTPException(status_code=404, detail="review item not found")
        if item.status != ReviewStatus.PENDING:
            raise HTTPException(status_code=409, detail="review item is already finalized")

        content = request.modified_content if request.modified_content is not None else item.content
        payload = dict(item.payload or {})
        if request.modified_payload:
            qdrant_payload = dict(payload.get("qdrant_payload") or {})
            qdrant_payload.update(request.modified_payload)
            payload["qdrant_payload"] = qdrant_payload

        next_status = {
            ReviewAction.APPROVE: ReviewStatus.APPROVED,
            ReviewAction.REJECT: ReviewStatus.REJECTED,
            ReviewAction.MODIFY: ReviewStatus.MODIFIED,
        }[request.action]

        finalized = self.repository.mark_review_item(
            item_id=item.id,
            status=next_status,
            reviewer_id=reviewer_id,
            content=content if request.action == ReviewAction.MODIFY else None,
            payload=payload,
        )

        if request.action in {ReviewAction.APPROVE, ReviewAction.MODIFY}:
            self._commit_reviewed_item(finalized)

        self.repository.record_audit_log(
            actor_id=reviewer_id,
            action="ITEM_REVIEW",
            status=AuditStatus.SUCCESS,
            resource_id=item.id,
            details={"review_action": request.action.value, "review_status": finalized.status.value},
        )
        return ReviewActionResponse(item_id=finalized.id, status=finalized.status)

    def _commit_reviewed_item(self, item: ReviewItemRecord) -> None:
        qdrant_payload = QdrantChunkPayload.model_validate(item.payload["qdrant_payload"])
        chunk_id = UUID(qdrant_payload.chunk_id)
        metadata = dict(item.payload.get("chunk_metadata") or {})
        metadata["review_status"] = item.status.value
        self.repository.update_chunk_content(chunk_id, item.content, metadata)
        vector = self.embedding_provider.embed([item.content])[0]
        self.vector_client.upsert_chunks([(chunk_id, vector, qdrant_payload)])
