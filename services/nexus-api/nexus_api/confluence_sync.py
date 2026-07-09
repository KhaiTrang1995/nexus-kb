from __future__ import annotations

import uuid
from pathlib import Path
from uuid import UUID

from nexus_confluence_bridge.bridge import sanitize_error
from nexus_shared.contracts import AuditStatus, SyncRunRecord, SyncRunStatus


class ConfluenceSyncService:
    """Pulls pages from a Confluence space into the existing ingestion_jobs
    queue -- each page becomes one staged .html file + one job, reusing the
    E1 markitdown HTML conversion and the E2 FIFO worker unchanged.

    Only orchestrates the *fetch* phase (creating jobs); actual parsing /
    chunking / embedding / publish-ack still happens asynchronously via
    JobWorker, same as any uploaded file.
    """

    def __init__(
        self,
        repository,
        confluence_client,
        staging_dir: str,
        max_attempts: int,
        page_limit: int = 100,
    ) -> None:
        self.repository = repository
        self.confluence_client = confluence_client
        self.staging_dir = staging_dir
        self.max_attempts = max_attempts
        self.page_limit = page_limit

    def sync(self, space_key: str, workspace_id: UUID, actor_id: str) -> SyncRunRecord:
        run = self.repository.create_sync_run(space_key, workspace_id, actor_id)
        self.repository.record_audit_log(
            actor_id=actor_id,
            action="SYNC_STARTED",
            status=AuditStatus.SUCCESS,
            resource_id=run.id,
            details={"space_key": space_key, "workspace_id": str(workspace_id)},
        )

        pages_seen = 0
        pages_indexed = 0
        try:
            pages = self.confluence_client.list_pages(space_key, self.page_limit)
            pages_seen = len(pages)

            staging_dir = Path(self.staging_dir)
            staging_dir.mkdir(parents=True, exist_ok=True)

            for page in pages:
                staged_path = staging_dir / f"{uuid.uuid4()}.html"
                staged_path.write_text(page.content, encoding="utf-8")
                self.repository.create_ingestion_job(
                    source_path=str(staged_path.resolve()),
                    original_filename=f"{page.title or page.id}.html",
                    file_extension=".html",
                    uploaded_by=f"confluence-sync:{actor_id}",
                    workspace_id=workspace_id,
                    max_attempts=self.max_attempts,
                    sync_run_id=run.id,
                )
                pages_indexed += 1

            finished = self.repository.finish_sync_run(
                run.id, SyncRunStatus.COMPLETED, pages_seen, pages_indexed
            )
            self.repository.record_audit_log(
                actor_id=actor_id,
                action="SYNC_COMPLETED",
                status=AuditStatus.SUCCESS,
                resource_id=run.id,
                details={"pages_seen": pages_seen, "pages_indexed": pages_indexed},
            )
            return finished
        except Exception as exc:
            error_message = sanitize_error(str(exc))
            finished = self.repository.finish_sync_run(
                run.id, SyncRunStatus.FAILED, pages_seen, pages_indexed, error_message
            )
            removed = self.repository.cleanup_sync_run(run.id)
            self.repository.record_audit_log(
                actor_id=actor_id,
                action="SYNC_FAILED",
                status=AuditStatus.FAILURE,
                resource_id=run.id,
                details={"error": error_message, "pages_seen": pages_seen, "documents_removed": removed},
            )
            return finished
