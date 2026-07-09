import unittest
from pathlib import Path
from uuid import UUID, uuid4

from tests import _paths  # noqa: F401

from nexus_document_parser.chunker import TextChunker
from nexus_document_parser.embedding import DeterministicEmbeddingProvider
from nexus_document_parser.job_worker import JobWorker
from nexus_document_parser.pipeline import IngestionPipeline
from nexus_shared.contracts import (
    AuditStatus,
    DocumentRecord,
    IngestionJobRecord,
    IngestionRunRecord,
    IngestionStatus,
    JobStatus,
)

FIXTURE_NOTE = str((Path(__file__).parent / "fixtures" / "pipeline" / "Note.md").resolve())
FIXTURE_PLAIN = str((Path(__file__).parent / "fixtures" / "plain" / "plain.txt").resolve())
DEFAULT_WORKSPACE_ID = uuid4()


class FakeJobRepository:
    def __init__(self) -> None:
        self.jobs: dict[UUID, dict] = {}
        self.documents_by_path: dict[str, DocumentRecord] = {}
        self.documents_by_id: dict[UUID, DocumentRecord] = {}
        self.document_versions: dict[UUID, list[dict]] = {}
        self.audit_events: list[str] = []
        self._queue_order: list[UUID] = []

    # -- job queue --
    def create_ingestion_job(
        self,
        source_path,
        original_filename,
        file_extension,
        uploaded_by,
        max_attempts,
        workspace_id=None,
        raw_content_hash=None,
        target_document_id=None,
    ):
        job_id = uuid4()
        self.jobs[job_id] = {
            "id": job_id,
            "source_path": source_path,
            "original_filename": original_filename,
            "file_extension": file_extension,
            "uploaded_by": uploaded_by,
            "workspace_id": workspace_id or DEFAULT_WORKSPACE_ID,
            "status": JobStatus.QUEUED,
            "attempt": 0,
            "max_attempts": max_attempts,
            "error_message": None,
            "document_id": None,
            "run_id": None,
            "raw_content_hash": raw_content_hash,
            "target_document_id": target_document_id,
        }
        self._queue_order.append(job_id)
        return IngestionJobRecord(**self.jobs[job_id])

    def get_ingestion_job(self, job_id):
        job = self.jobs.get(job_id)
        return None if job is None else IngestionJobRecord(**job)

    def queue_position(self, job_id):
        job = self.jobs.get(job_id)
        if job is None or job["status"] != JobStatus.QUEUED:
            return None
        queued_ids = [jid for jid in self._queue_order if self.jobs[jid]["status"] == JobStatus.QUEUED]
        return queued_ids.index(job_id) + 1

    def claim_next_job(self):
        for job_id in self._queue_order:
            job = self.jobs[job_id]
            if job["status"] == JobStatus.QUEUED:
                job["status"] = JobStatus.EXTRACTING
                job["attempt"] += 1
                return IngestionJobRecord(**job)
        return None

    def complete_job(self, job_id, document_id, run_id):
        job = self.jobs[job_id]
        job["status"] = JobStatus.INDEXED
        job["document_id"] = document_id
        job["run_id"] = run_id
        job["error_message"] = None
        return IngestionJobRecord(**job)

    def fail_job(self, job_id, error_message):
        job = self.jobs[job_id]
        job["error_message"] = error_message
        if job["attempt"] < job["max_attempts"]:
            job["status"] = JobStatus.QUEUED
        else:
            job["status"] = JobStatus.FAILED
        return IngestionJobRecord(**job)

    def retry_job(self, job_id):
        job = self.jobs[job_id]
        if job["status"] != JobStatus.FAILED:
            raise ValueError("only failed jobs can be retried")
        job["status"] = JobStatus.QUEUED
        job["attempt"] = 0
        job["error_message"] = None
        self._queue_order.remove(job_id)
        self._queue_order.append(job_id)
        return IngestionJobRecord(**job)

    # -- documents --
    def delete_document_by_source_path(self, source_path):
        existing = self.documents_by_path.pop(source_path, None)
        if existing is not None:
            self.documents_by_id.pop(existing.id, None)

    def get_document_by_source_path(self, source_path):
        return self.documents_by_path.get(source_path)

    def get_document(self, document_id):
        return self.documents_by_id.get(document_id)

    def upsert_document(self, document, workspace_id=None, uploaded_by=None):
        existing = self.documents_by_path.get(document.source_path)
        if existing and existing.content_hash == document.content_hash:
            return existing, False
        record = DocumentRecord(
            id=existing.id if existing else uuid4(),
            source_type=document.source_type,
            source_path=document.source_path,
            file_extension=document.file_extension,
            mime_type=document.mime_type,
            title=document.title,
            content_hash=document.content_hash,
            frontmatter=document.frontmatter,
            tags=document.tags,
            workspace_id=workspace_id,
            uploaded_by=uploaded_by,
            wikilinks=document.wikilinks,
        )
        self.documents_by_path[document.source_path] = record
        self.documents_by_id[record.id] = record
        return record, True

    def find_indexed_job_by_raw_hash(self, raw_content_hash):
        for job_id in self._queue_order:
            job = self.jobs[job_id]
            if job["status"] == JobStatus.INDEXED and job.get("raw_content_hash") == raw_content_hash:
                return IngestionJobRecord(**job)
        return None

    def upsert_document_version(self, target_document_id, document, uploaded_by=None):
        existing = self.documents_by_id[target_document_id]
        self.document_versions.setdefault(target_document_id, []).append(
            {
                "version_number": existing.current_version,
                "title": existing.title,
                "content_hash": existing.content_hash,
                "file_extension": existing.file_extension,
                "mime_type": existing.mime_type,
                "source_path": existing.source_path,
                "uploaded_by": existing.uploaded_by,
                "acked_by": existing.acked_by,
                "acked_at": existing.acked_at,
            }
        )
        self.documents_by_path.pop(existing.source_path, None)
        updated = DocumentRecord(
            id=existing.id,
            source_type=document.source_type,
            source_path=document.source_path,
            file_extension=document.file_extension,
            mime_type=document.mime_type,
            title=document.title,
            content_hash=document.content_hash,
            frontmatter=document.frontmatter,
            tags=document.tags,
            wikilinks=document.wikilinks,
            current_version=existing.current_version + 1,
            workspace_id=existing.workspace_id,
            uploaded_by=uploaded_by,
            acked_by=None,
            acked_at=None,
        )
        self.documents_by_id[target_document_id] = updated
        self.documents_by_path[document.source_path] = updated
        return updated, True

    def rollback_failed_version(self, document_id):
        existing = self.documents_by_id.get(document_id)
        if existing is None or existing.current_version <= 1:
            return
        snapshots = self.document_versions.get(document_id, [])
        index = next(
            (i for i, snap in enumerate(snapshots) if snap["version_number"] == existing.current_version - 1),
            None,
        )
        if index is None:
            return
        snapshot = snapshots.pop(index)
        self.documents_by_path.pop(existing.source_path, None)
        restored = DocumentRecord(
            id=existing.id,
            source_type=existing.source_type,
            source_path=snapshot["source_path"],
            file_extension=snapshot["file_extension"],
            mime_type=snapshot["mime_type"],
            title=snapshot["title"],
            content_hash=snapshot["content_hash"],
            frontmatter=existing.frontmatter,
            tags=existing.tags,
            wikilinks=existing.wikilinks,
            current_version=snapshot["version_number"],
            workspace_id=existing.workspace_id,
            uploaded_by=snapshot["uploaded_by"],
            acked_by=snapshot["acked_by"],
            acked_at=snapshot["acked_at"],
        )
        self.documents_by_id[document_id] = restored
        self.documents_by_path[snapshot["source_path"]] = restored

    # -- pipeline plumbing --
    def create_ingestion_run(self, source_path):
        return IngestionRunRecord(id=uuid4(), source_path=source_path, status=IngestionStatus.RUNNING)

    def finish_ingestion_run(self, run_id, status, documents_seen, documents_indexed, chunks_indexed, error_message=None):
        return IngestionRunRecord(
            id=run_id,
            source_path="source",
            status=status,
            documents_seen=documents_seen,
            documents_indexed=documents_indexed,
            chunks_indexed=chunks_indexed,
            error_message=error_message,
        )

    def replace_chunks(self, document_id, chunks, embedding_model):
        return [(uuid4(), chunk) for chunk in chunks]

    def record_audit_log(self, actor_id, action, status, resource_id=None, details=None):
        self.audit_events.append(action)


class FakeVectorClient:
    def __init__(self) -> None:
        self.points = []

    def upsert_chunks(self, points):
        self.points.extend(points)


def make_pipeline(repository: FakeJobRepository) -> IngestionPipeline:
    return IngestionPipeline(
        repository=repository,
        vector_client=FakeVectorClient(),
        embedding_provider=DeterministicEmbeddingProvider(dimension=8),
        chunker=TextChunker(max_chars=200, overlap_chars=20),
    )


class JobWorkerTest(unittest.TestCase):
    def test_returns_none_when_queue_is_empty(self) -> None:
        repository = FakeJobRepository()
        worker = JobWorker(repository, make_pipeline(repository))

        self.assertIsNone(worker.run_once())

    def test_processes_job_to_indexed_on_success(self) -> None:
        repository = FakeJobRepository()
        job = repository.create_ingestion_job(FIXTURE_NOTE, "Note.md", ".md", uploaded_by="tester@nexus", max_attempts=3)
        worker = JobWorker(repository, make_pipeline(repository))

        updated = worker.run_once()

        self.assertEqual(updated.id, job.id)
        self.assertEqual(updated.status, JobStatus.INDEXED)
        self.assertIsNotNone(updated.document_id)
        self.assertIsNotNone(updated.run_id)
        self.assertIn("JOB_INDEXED", repository.audit_events)

    def test_newly_indexed_chunks_are_unpublished_until_acked(self) -> None:
        repository = FakeJobRepository()
        repository.create_ingestion_job(FIXTURE_NOTE, "Note.md", ".md", uploaded_by="tester@nexus", max_attempts=3)
        vector_client = FakeVectorClient()
        pipeline = IngestionPipeline(
            repository=repository,
            vector_client=vector_client,
            embedding_provider=DeterministicEmbeddingProvider(dimension=8),
            chunker=TextChunker(max_chars=200, overlap_chars=20),
        )
        worker = JobWorker(repository, pipeline)

        worker.run_once()

        self.assertGreater(len(vector_client.points), 0)
        for _, _, payload in vector_client.points:
            self.assertFalse(payload.published)

    def test_document_uploaded_by_matches_job_uploader(self) -> None:
        repository = FakeJobRepository()
        job = repository.create_ingestion_job(FIXTURE_NOTE, "Note.md", ".md", uploaded_by="tester@nexus", max_attempts=3)
        worker = JobWorker(repository, make_pipeline(repository))

        updated = worker.run_once()

        document = repository.documents_by_id[updated.document_id]
        self.assertEqual(document.uploaded_by, job.uploaded_by)
        self.assertIsNone(document.acked_at)

    def test_fifo_order_claims_oldest_job_first(self) -> None:
        repository = FakeJobRepository()
        first = repository.create_ingestion_job(FIXTURE_NOTE, "Note.md", ".md", uploaded_by="tester@nexus", max_attempts=3)
        second = repository.create_ingestion_job("/nonexistent/second.md", "second.md", ".md", uploaded_by="tester@nexus", max_attempts=3)
        worker = JobWorker(repository, make_pipeline(repository))

        updated = worker.run_once()

        self.assertEqual(updated.id, first.id)
        self.assertEqual(repository.queue_position(second.id), 1)

    def test_requeues_on_failure_until_max_attempts_then_marks_failed(self) -> None:
        repository = FakeJobRepository()
        repository.create_ingestion_job("/nonexistent/missing.md", "missing.md", ".md", uploaded_by="tester@nexus", max_attempts=3)
        worker = JobWorker(repository, make_pipeline(repository))

        first_attempt = worker.run_once()
        self.assertEqual(first_attempt.status, JobStatus.QUEUED)
        self.assertEqual(first_attempt.attempt, 1)
        self.assertIn("does not exist", first_attempt.error_message)

        second_attempt = worker.run_once()
        self.assertEqual(second_attempt.status, JobStatus.QUEUED)
        self.assertEqual(second_attempt.attempt, 2)

        third_attempt = worker.run_once()
        self.assertEqual(third_attempt.status, JobStatus.FAILED)
        self.assertEqual(third_attempt.attempt, 3)
        self.assertIn("JOB_FAILED", repository.audit_events)

    def test_manual_retry_resets_failed_job_to_queued(self) -> None:
        repository = FakeJobRepository()
        job = repository.create_ingestion_job("/nonexistent/missing.md", "missing.md", ".md", uploaded_by="tester@nexus", max_attempts=1)
        worker = JobWorker(repository, make_pipeline(repository))

        failed = worker.run_once()
        self.assertEqual(failed.status, JobStatus.FAILED)

        retried = repository.retry_job(job.id)
        self.assertEqual(retried.status, JobStatus.QUEUED)
        self.assertEqual(retried.attempt, 0)
        self.assertIsNone(retried.error_message)

    def test_cleans_up_document_created_before_a_later_failure(self) -> None:
        # Simulate: upsert_document succeeded, but something downstream failed --
        # the job must not leave an orphaned document row behind.
        repository = FakeJobRepository()
        repository.documents_by_path[FIXTURE_NOTE] = DocumentRecord(
            id=uuid4(),
            source_type="local_file",
            source_path=FIXTURE_NOTE,
            file_extension=".md",
            mime_type="text/markdown",
            title="stale",
            content_hash="stale-hash",
        )
        job = repository.create_ingestion_job(FIXTURE_NOTE, "Note.md", ".md", uploaded_by="tester@nexus", max_attempts=3)

        class ExplodingVectorClient:
            def upsert_chunks(self, points):
                raise RuntimeError("qdrant unavailable")

        pipeline = IngestionPipeline(
            repository=repository,
            vector_client=ExplodingVectorClient(),
            embedding_provider=DeterministicEmbeddingProvider(dimension=8),
            chunker=TextChunker(max_chars=200, overlap_chars=20),
        )
        worker = JobWorker(repository, pipeline)

        updated = worker.run_once()

        self.assertEqual(updated.status, JobStatus.QUEUED)
        self.assertIsNone(repository.get_document_by_source_path(FIXTURE_NOTE))

    def test_version_bump_success_creates_snapshot_and_bumps_version(self) -> None:
        repository = FakeJobRepository()
        repository.create_ingestion_job(FIXTURE_NOTE, "Note.md", ".md", uploaded_by="tester@nexus", max_attempts=3)
        worker = JobWorker(repository, make_pipeline(repository))
        first_result = worker.run_once()
        document_id = first_result.document_id
        self.assertEqual(repository.documents_by_id[document_id].current_version, 1)

        repository.create_ingestion_job(
            FIXTURE_PLAIN,
            "plain.txt",
            ".txt",
            uploaded_by="tester@nexus",
            max_attempts=3,
            target_document_id=document_id,
        )
        second_result = worker.run_once()

        self.assertEqual(second_result.status, JobStatus.INDEXED)
        self.assertEqual(second_result.document_id, document_id)
        updated_document = repository.documents_by_id[document_id]
        self.assertEqual(updated_document.current_version, 2)
        snapshots = repository.document_versions[document_id]
        self.assertEqual(len(snapshots), 1)
        self.assertEqual(snapshots[0]["version_number"], 1)

    def test_version_bump_failure_rolls_back_to_previous_snapshot(self) -> None:
        repository = FakeJobRepository()
        repository.create_ingestion_job(FIXTURE_NOTE, "Note.md", ".md", uploaded_by="tester@nexus", max_attempts=3)
        worker = JobWorker(repository, make_pipeline(repository))
        first_result = worker.run_once()
        document_id = first_result.document_id
        original_content_hash = repository.documents_by_id[document_id].content_hash

        repository.create_ingestion_job(
            FIXTURE_PLAIN,
            "plain.txt",
            ".txt",
            uploaded_by="tester@nexus",
            max_attempts=1,
            target_document_id=document_id,
        )

        class ExplodingVectorClient:
            def upsert_chunks(self, points):
                raise RuntimeError("qdrant unavailable")

        pipeline = IngestionPipeline(
            repository=repository,
            vector_client=ExplodingVectorClient(),
            embedding_provider=DeterministicEmbeddingProvider(dimension=8),
            chunker=TextChunker(max_chars=200, overlap_chars=20),
        )
        failing_worker = JobWorker(repository, pipeline)

        result = failing_worker.run_once()

        self.assertEqual(result.status, JobStatus.FAILED)
        restored = repository.documents_by_id[document_id]
        self.assertEqual(restored.current_version, 1)
        self.assertEqual(restored.content_hash, original_content_hash)
        self.assertEqual(repository.document_versions.get(document_id, []), [])


if __name__ == "__main__":
    unittest.main()
