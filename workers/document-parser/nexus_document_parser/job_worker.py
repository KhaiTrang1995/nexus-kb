from __future__ import annotations

import logging
import time

from nexus_shared.contracts import AuditStatus, IngestionJobRecord, IngestionStatus, SourceType
from nexus_document_parser.pipeline import IngestionPipeline
from nexus_document_parser.ports import MetadataRepository

logger = logging.getLogger(__name__)


class JobWorker:
    """Claims one ingestion_jobs row at a time and runs it through IngestionPipeline.

    Each job's source_path is a single staged file, so IngestionPipeline's existing
    single-file branch (not the directory scan) does the actual parse/chunk/embed/upsert
    work. This worker only owns queue state transitions and cleanup on failure.
    """

    def __init__(
        self,
        repository: MetadataRepository,
        pipeline: IngestionPipeline,
        actor_id: str = "system:job-worker",
    ) -> None:
        self.repository = repository
        self.pipeline = pipeline
        self.actor_id = actor_id

    def run_once(self) -> IngestionJobRecord | None:
        job = self.repository.claim_next_job()
        if job is None:
            return None

        self.repository.record_audit_log(
            actor_id=self.actor_id,
            action="JOB_STARTED",
            status=AuditStatus.SUCCESS,
            resource_id=job.id,
            details={"source_path": job.source_path, "attempt": job.attempt},
        )

        result = self.pipeline.ingest(
            job.source_path,
            SourceType.LOCAL_FILE,
            target_document_id=job.target_document_id,
            workspace_id=job.workspace_id,
            uploaded_by=job.uploaded_by,
        )

        if result.status == IngestionStatus.COMPLETED:
            document = self.repository.get_document_by_source_path(job.source_path)
            if document is not None:
                updated = self.repository.complete_job(job.id, document.id, result.run_id)
                self.repository.record_audit_log(
                    actor_id=self.actor_id,
                    action="JOB_INDEXED",
                    status=AuditStatus.SUCCESS,
                    resource_id=job.id,
                    details={"document_id": str(document.id), "run_id": str(result.run_id)},
                )
                return updated
            error_message = "ingestion completed but produced no document"
        else:
            error_message = result.error_message or "ingestion failed"

        if job.target_document_id is not None:
            # Version bump failed after overwriting the live row: restore the
            # snapshot taken moments ago instead of deleting the document
            # outright (it may have earlier, successfully-indexed history).
            self.repository.rollback_failed_version(job.target_document_id)
        else:
            # Brand-new upload failed: nothing else references this document yet,
            # so delete it outright. ChunkModel FK cascades on delete.
            self.repository.delete_document_by_source_path(job.source_path)
        updated = self.repository.fail_job(job.id, error_message)
        self.repository.record_audit_log(
            actor_id=self.actor_id,
            action="JOB_FAILED" if updated.status.value == "failed" else "JOB_REQUEUED",
            status=AuditStatus.FAILURE,
            resource_id=job.id,
            details={"error": error_message, "attempt": updated.attempt, "max_attempts": updated.max_attempts},
        )
        return updated

    def run_forever(self, poll_interval_seconds: float = 2.0) -> None:
        while True:
            job = self.run_once()
            if job is None:
                time.sleep(poll_interval_seconds)
