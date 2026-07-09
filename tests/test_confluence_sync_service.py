from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from uuid import uuid4

from tests import _paths  # noqa: F401

from nexus_api.confluence_sync import ConfluenceSyncService
from nexus_shared.contracts import SyncRunRecord, SyncRunStatus


class FakePage:
    def __init__(self, id: str, title: str, content: str) -> None:
        self.id = id
        self.title = title
        self.content = content


class FakeConfluenceClient:
    def __init__(self, pages: list[FakePage] | None = None, error: Exception | None = None) -> None:
        self.pages = pages or []
        self.error = error

    def list_pages(self, space_key: str, limit: int) -> list[FakePage]:
        if self.error is not None:
            raise self.error
        return self.pages[:limit]


class FakeSyncRepository:
    def __init__(self) -> None:
        self.jobs_created: list[dict] = []
        self.audit_events: list[str] = []
        self.finished_runs: list[tuple] = []
        self.cleaned_up_runs: list = []
        self._run_id = uuid4()

    def create_sync_run(self, space_key, workspace_id, actor_id):
        return SyncRunRecord(
            id=self._run_id,
            space_key=space_key,
            workspace_id=workspace_id,
            status=SyncRunStatus.RUNNING,
            actor_id=actor_id,
        )

    def create_ingestion_job(self, **kwargs):
        self.jobs_created.append(kwargs)
        return None

    def finish_sync_run(self, sync_run_id, status, pages_seen, pages_indexed, error_message=None):
        self.finished_runs.append((status, pages_seen, pages_indexed, error_message))
        return SyncRunRecord(
            id=sync_run_id,
            space_key="KB",
            workspace_id=uuid4(),
            status=status,
            actor_id="admin",
            pages_seen=pages_seen,
            pages_indexed=pages_indexed,
            error_message=error_message,
        )

    def cleanup_sync_run(self, sync_run_id):
        self.cleaned_up_runs.append(sync_run_id)
        return 0

    def record_audit_log(self, actor_id, action, status, resource_id=None, details=None):
        self.audit_events.append(action)


class ConfluenceSyncServiceTest(unittest.TestCase):
    def setUp(self) -> None:
        self._tmpdir = tempfile.TemporaryDirectory()

    def tearDown(self) -> None:
        self._tmpdir.cleanup()

    def test_successful_sync_creates_one_job_per_page_and_completes(self) -> None:
        repository = FakeSyncRepository()
        client = FakeConfluenceClient(
            pages=[FakePage("1", "Runbook", "<p>a</p>"), FakePage("2", "Guide", "<p>b</p>")]
        )
        service = ConfluenceSyncService(
            repository=repository,
            confluence_client=client,
            staging_dir=self._tmpdir.name,
            max_attempts=3,
        )

        result = service.sync("KB", uuid4(), actor_id="admin")

        self.assertEqual(result.status, SyncRunStatus.COMPLETED)
        self.assertEqual(len(repository.jobs_created), 2)
        for job in repository.jobs_created:
            self.assertEqual(job["file_extension"], ".html")
            self.assertTrue(job["uploaded_by"].startswith("confluence-sync:"))
            self.assertTrue(Path(job["source_path"]).exists())
        self.assertIn("SYNC_STARTED", repository.audit_events)
        self.assertIn("SYNC_COMPLETED", repository.audit_events)
        self.assertEqual(repository.cleaned_up_runs, [])

    def test_fetch_failure_marks_run_failed_and_cleans_up(self) -> None:
        repository = FakeSyncRepository()
        client = FakeConfluenceClient(error=RuntimeError("https://example.atlassian.net/wiki timeout token=abc123"))
        service = ConfluenceSyncService(
            repository=repository,
            confluence_client=client,
            staging_dir=self._tmpdir.name,
            max_attempts=3,
        )

        result = service.sync("KB", uuid4(), actor_id="admin")

        self.assertEqual(result.status, SyncRunStatus.FAILED)
        self.assertEqual(len(repository.cleaned_up_runs), 1)
        self.assertIn("SYNC_FAILED", repository.audit_events)
        status, pages_seen, pages_indexed, error_message = repository.finished_runs[0]
        self.assertEqual(status, SyncRunStatus.FAILED)
        self.assertNotIn("token=abc123", error_message)
        self.assertNotIn("https://example.atlassian.net", error_message)


if __name__ == "__main__":
    unittest.main()
