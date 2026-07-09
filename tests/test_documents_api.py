from __future__ import annotations

import tempfile
import unittest
from unittest.mock import MagicMock, patch
from uuid import uuid4

from fastapi.testclient import TestClient

from tests import _paths  # noqa: F401

from nexus_api.config import Settings
from nexus_api.main import app
from nexus_shared.contracts import DocumentRecord, DocumentVersionRecord, IngestionJobRecord, JobStatus

DEFAULT_WORKSPACE_ID = uuid4()
ADMIN_HEADERS = {"X-User-Id": "u1", "X-Is-Admin": "true"}


def make_job(**overrides) -> IngestionJobRecord:
    defaults = dict(
        id=uuid4(),
        source_path="/data/uploads/staged.txt",
        original_filename="staged.txt",
        file_extension=".txt",
        uploaded_by="u1",
        workspace_id=DEFAULT_WORKSPACE_ID,
        status=JobStatus.QUEUED,
        attempt=0,
        max_attempts=3,
    )
    defaults.update(overrides)
    return IngestionJobRecord(**defaults)


class UploadDocumentsApiTest(unittest.TestCase):
    def setUp(self) -> None:
        self._tmpdir = tempfile.TemporaryDirectory()
        self.settings = Settings(upload_staging_dir=self._tmpdir.name)

    def tearDown(self) -> None:
        self._tmpdir.cleanup()

    def test_uploads_valid_files_and_creates_one_job_per_file(self) -> None:
        repo = MagicMock()
        repo.find_indexed_job_by_raw_hash.return_value = None
        repo.create_ingestion_job.side_effect = [
            make_job(original_filename="a.txt"),
            make_job(original_filename="b.md"),
        ]

        with (
            patch("nexus_api.routers.documents.build_repository", return_value=repo),
            patch("nexus_api.routers.documents.get_settings", return_value=self.settings),
        ):
            response = TestClient(app).post(
                "/api/v1/documents",
                files=[
                    ("files", ("a.txt", b"hello world", "text/plain")),
                    ("files", ("b.md", b"# hello", "text/markdown")),
                ],
                data={"workspace_id": str(DEFAULT_WORKSPACE_ID)},
                headers=ADMIN_HEADERS,
            )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(len(payload["jobs"]), 2)
        self.assertEqual(payload["rejected"], [])
        self.assertEqual(repo.create_ingestion_job.call_count, 2)
        _, kwargs = repo.create_ingestion_job.call_args_list[0]
        self.assertEqual(kwargs["uploaded_by"], "u1")
        self.assertEqual(kwargs["original_filename"], "a.txt")
        self.assertEqual(kwargs["workspace_id"], DEFAULT_WORKSPACE_ID)

    def test_rejects_unsupported_extension_but_keeps_valid_files(self) -> None:
        repo = MagicMock()
        repo.find_indexed_job_by_raw_hash.return_value = None
        repo.create_ingestion_job.side_effect = [make_job(original_filename="a.txt")]

        with (
            patch("nexus_api.routers.documents.build_repository", return_value=repo),
            patch("nexus_api.routers.documents.get_settings", return_value=self.settings),
        ):
            response = TestClient(app).post(
                "/api/v1/documents",
                files=[
                    ("files", ("a.txt", b"hello", "text/plain")),
                    ("files", ("virus.exe", b"binary", "application/octet-stream")),
                ],
                data={"workspace_id": str(DEFAULT_WORKSPACE_ID)},
                headers=ADMIN_HEADERS,
            )

        payload = response.json()
        self.assertEqual(len(payload["jobs"]), 1)
        self.assertEqual(len(payload["rejected"]), 1)
        self.assertIn("virus.exe", payload["rejected"][0])

    def test_rejects_empty_file(self) -> None:
        repo = MagicMock()
        with (
            patch("nexus_api.routers.documents.build_repository", return_value=repo),
            patch("nexus_api.routers.documents.get_settings", return_value=self.settings),
        ):
            response = TestClient(app).post(
                "/api/v1/documents",
                files=[("files", ("empty.txt", b"", "text/plain"))],
                data={"workspace_id": str(DEFAULT_WORKSPACE_ID)},
                headers=ADMIN_HEADERS,
            )

        payload = response.json()
        self.assertEqual(payload["jobs"], [])
        self.assertIn("rong", payload["rejected"][0])
        repo.create_ingestion_job.assert_not_called()

    def test_rejects_oversized_file(self) -> None:
        settings = Settings(upload_staging_dir=self._tmpdir.name, upload_max_file_size_mb=0)
        repo = MagicMock()
        with (
            patch("nexus_api.routers.documents.build_repository", return_value=repo),
            patch("nexus_api.routers.documents.get_settings", return_value=settings),
        ):
            response = TestClient(app).post(
                "/api/v1/documents",
                files=[("files", ("big.txt", b"x" * 10, "text/plain"))],
                data={"workspace_id": str(DEFAULT_WORKSPACE_ID)},
                headers=ADMIN_HEADERS,
            )

        payload = response.json()
        self.assertEqual(payload["jobs"], [])
        self.assertIn("dung luong", payload["rejected"][0])

    def test_rejects_whole_batch_when_over_file_count_limit(self) -> None:
        settings = Settings(upload_staging_dir=self._tmpdir.name, upload_max_files_per_batch=1)
        repo = MagicMock()
        with (
            patch("nexus_api.routers.documents.build_repository", return_value=repo),
            patch("nexus_api.routers.documents.get_settings", return_value=settings),
        ):
            response = TestClient(app).post(
                "/api/v1/documents",
                files=[
                    ("files", ("a.txt", b"hello", "text/plain")),
                    ("files", ("b.txt", b"world", "text/plain")),
                ],
                data={"workspace_id": str(DEFAULT_WORKSPACE_ID)},
                headers=ADMIN_HEADERS,
            )

        self.assertEqual(response.status_code, 400)
        repo.create_ingestion_job.assert_not_called()

    def test_duplicate_content_is_reported_and_not_queued(self) -> None:
        existing_document_id = uuid4()
        repo = MagicMock()
        repo.find_indexed_job_by_raw_hash.return_value = make_job(
            status=JobStatus.INDEXED, document_id=existing_document_id
        )
        repo.get_document.return_value = DocumentRecord(
            id=existing_document_id,
            source_type="local_file",
            source_path="/data/uploads/prior.txt",
            file_extension=".txt",
            mime_type="text/plain",
            title="Prior Document",
            content_hash="deadbeef",
        )

        with (
            patch("nexus_api.routers.documents.build_repository", return_value=repo),
            patch("nexus_api.routers.documents.get_settings", return_value=self.settings),
        ):
            response = TestClient(app).post(
                "/api/v1/documents",
                files=[("files", ("dup.txt", b"same content", "text/plain"))],
                data={"workspace_id": str(DEFAULT_WORKSPACE_ID)},
                headers=ADMIN_HEADERS,
            )

        payload = response.json()
        self.assertEqual(payload["jobs"], [])
        self.assertEqual(len(payload["duplicates"]), 1)
        self.assertEqual(payload["duplicates"][0]["existing_document_id"], str(existing_document_id))
        self.assertEqual(payload["duplicates"][0]["existing_document_title"], "Prior Document")
        repo.create_ingestion_job.assert_not_called()

    def test_confirm_version_of_bypasses_duplicate_check_and_targets_document(self) -> None:
        existing_document_id = uuid4()
        repo = MagicMock()
        repo.get_document.return_value = DocumentRecord(
            id=existing_document_id,
            source_type="local_file",
            source_path="/data/uploads/prior.txt",
            file_extension=".txt",
            mime_type="text/plain",
            title="Prior Document",
            content_hash="deadbeef",
            workspace_id=DEFAULT_WORKSPACE_ID,
        )
        repo.create_ingestion_job.return_value = make_job(target_document_id=existing_document_id)

        with (
            patch("nexus_api.routers.documents.build_repository", return_value=repo),
            patch("nexus_api.routers.documents.get_settings", return_value=self.settings),
        ):
            response = TestClient(app).post(
                "/api/v1/documents",
                files=[("files", ("dup.txt", b"same content", "text/plain"))],
                data={"workspace_id": str(DEFAULT_WORKSPACE_ID), "confirm_version_of": str(existing_document_id)},
                headers=ADMIN_HEADERS,
            )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(len(payload["jobs"]), 1)
        self.assertEqual(payload["duplicates"], [])
        repo.find_indexed_job_by_raw_hash.assert_not_called()
        _, kwargs = repo.create_ingestion_job.call_args
        self.assertEqual(kwargs["target_document_id"], existing_document_id)


class WorkspaceAccessControlTest(unittest.TestCase):
    """Flagship RBAC test: a member of one workspace must never see/act on another's data."""

    def setUp(self) -> None:
        self._tmpdir = tempfile.TemporaryDirectory()
        self.settings = Settings(upload_staging_dir=self._tmpdir.name)
        self.workspace_a = uuid4()
        self.workspace_b = uuid4()

    def tearDown(self) -> None:
        self._tmpdir.cleanup()

    def test_member_cannot_upload_into_a_workspace_they_do_not_belong_to(self) -> None:
        repo = MagicMock()
        with (
            patch("nexus_api.routers.documents.build_repository", return_value=repo),
            patch("nexus_api.routers.documents.get_settings", return_value=self.settings),
        ):
            response = TestClient(app).post(
                "/api/v1/documents",
                files=[("files", ("a.txt", b"hello", "text/plain"))],
                data={"workspace_id": str(self.workspace_b)},
                headers={"X-User-Id": "member-a", "X-Workspace-Ids": str(self.workspace_a)},
            )

        self.assertEqual(response.status_code, 403)
        repo.create_ingestion_job.assert_not_called()

    def test_member_can_upload_into_their_own_workspace(self) -> None:
        repo = MagicMock()
        repo.find_indexed_job_by_raw_hash.return_value = None
        repo.create_ingestion_job.return_value = make_job(workspace_id=self.workspace_a)

        with (
            patch("nexus_api.routers.documents.build_repository", return_value=repo),
            patch("nexus_api.routers.documents.get_settings", return_value=self.settings),
        ):
            response = TestClient(app).post(
                "/api/v1/documents",
                files=[("files", ("a.txt", b"hello", "text/plain"))],
                data={"workspace_id": str(self.workspace_a)},
                headers={"X-User-Id": "member-a", "X-Workspace-Ids": str(self.workspace_a)},
            )

        self.assertEqual(response.status_code, 200)

    def test_cannot_version_a_document_belonging_to_another_workspace(self) -> None:
        other_document_id = uuid4()
        repo = MagicMock()
        repo.get_document.return_value = DocumentRecord(
            id=other_document_id,
            source_type="local_file",
            source_path="/data/uploads/b.txt",
            file_extension=".txt",
            mime_type="text/plain",
            title="Workspace B Document",
            content_hash="hash",
            workspace_id=self.workspace_b,
        )

        with (
            patch("nexus_api.routers.documents.build_repository", return_value=repo),
            patch("nexus_api.routers.documents.get_settings", return_value=self.settings),
        ):
            response = TestClient(app).post(
                "/api/v1/documents",
                files=[("files", ("b.txt", b"hello", "text/plain"))],
                data={"workspace_id": str(self.workspace_a), "confirm_version_of": str(other_document_id)},
                headers={"X-User-Id": "member-a", "X-Workspace-Ids": str(self.workspace_a)},
            )

        self.assertEqual(response.status_code, 400)
        repo.create_ingestion_job.assert_not_called()

    def test_admin_bypasses_workspace_membership_check(self) -> None:
        repo = MagicMock()
        repo.find_indexed_job_by_raw_hash.return_value = None
        repo.create_ingestion_job.return_value = make_job(workspace_id=self.workspace_b)

        with (
            patch("nexus_api.routers.documents.build_repository", return_value=repo),
            patch("nexus_api.routers.documents.get_settings", return_value=self.settings),
        ):
            response = TestClient(app).post(
                "/api/v1/documents",
                files=[("files", ("a.txt", b"hello", "text/plain"))],
                data={"workspace_id": str(self.workspace_b)},
                headers={"X-User-Id": "root", "X-Is-Admin": "true"},
            )

        self.assertEqual(response.status_code, 200)

    def test_member_cannot_see_job_status_from_another_workspace(self) -> None:
        job = make_job(workspace_id=self.workspace_b)
        repo = MagicMock()
        repo.get_ingestion_job.return_value = job

        with patch("nexus_api.routers.documents.build_repository", return_value=repo):
            response = TestClient(app).get(
                f"/api/v1/jobs/{job.id}",
                headers={"X-User-Id": "member-a", "X-Workspace-Ids": str(self.workspace_a)},
            )

        self.assertEqual(response.status_code, 403)

    def test_member_cannot_see_version_history_from_another_workspace(self) -> None:
        document_id = uuid4()
        repo = MagicMock()
        repo.list_document_versions.return_value = [
            DocumentVersionRecord(
                document_id=document_id,
                workspace_id=self.workspace_b,
                version_number=1,
                title="Doc",
                content_hash="hash",
                file_extension=".txt",
                mime_type="text/plain",
                source_path="/data/uploads/b.txt",
                is_current=True,
            )
        ]

        with patch("nexus_api.routers.documents.build_repository", return_value=repo):
            response = TestClient(app).get(
                f"/api/v1/documents/{document_id}/versions",
                headers={"X-User-Id": "member-a", "X-Workspace-Ids": str(self.workspace_a)},
            )

        self.assertEqual(response.status_code, 403)


class DocumentVersionsApiTest(unittest.TestCase):
    def test_returns_version_history_newest_first(self) -> None:
        document_id = uuid4()
        repo = MagicMock()
        repo.list_document_versions.return_value = [
            DocumentVersionRecord(
                document_id=document_id,
                workspace_id=DEFAULT_WORKSPACE_ID,
                version_number=2,
                title="Doc v2",
                content_hash="hash2",
                file_extension=".txt",
                mime_type="text/plain",
                source_path="/data/uploads/v2.txt",
                is_current=True,
            ),
            DocumentVersionRecord(
                document_id=document_id,
                workspace_id=DEFAULT_WORKSPACE_ID,
                version_number=1,
                title="Doc v1",
                content_hash="hash1",
                file_extension=".txt",
                mime_type="text/plain",
                source_path="/data/uploads/v1.txt",
                is_current=False,
            ),
        ]

        with patch("nexus_api.routers.documents.build_repository", return_value=repo):
            response = TestClient(app).get(
                f"/api/v1/documents/{document_id}/versions", headers=ADMIN_HEADERS
            )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(len(payload["versions"]), 2)
        self.assertTrue(payload["versions"][0]["is_current"])
        self.assertEqual(payload["versions"][1]["version_number"], 1)

    def test_returns_404_when_document_has_no_versions(self) -> None:
        repo = MagicMock()
        repo.list_document_versions.return_value = []

        with patch("nexus_api.routers.documents.build_repository", return_value=repo):
            response = TestClient(app).get(f"/api/v1/documents/{uuid4()}/versions", headers=ADMIN_HEADERS)

        self.assertEqual(response.status_code, 404)


class DocumentAckApiTest(unittest.TestCase):
    def test_uploader_can_ack_their_own_document(self) -> None:
        document_id = uuid4()
        document = DocumentRecord(
            id=document_id,
            source_type="local_file",
            source_path="/data/uploads/a.txt",
            file_extension=".txt",
            mime_type="text/plain",
            title="A",
            content_hash="hash",
            uploaded_by="u1",
        )
        acked_document = document.model_copy(update={"acked_by": "u1"})
        repo = MagicMock()
        repo.get_document.return_value = document
        repo.ack_document.return_value = (acked_document, [uuid4()])
        vector_client = MagicMock()

        with (
            patch("nexus_api.routers.documents.build_repository", return_value=repo),
            patch("nexus_api.routers.documents.build_vector_client", return_value=vector_client),
        ):
            response = TestClient(app).post(
                f"/api/v1/documents/{document_id}/ack", headers={"X-User-Id": "u1"}
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["acked_by"], "u1")
        vector_client.set_payload.assert_called_once()

    def test_other_member_cannot_ack_someone_elses_document(self) -> None:
        document_id = uuid4()
        document = DocumentRecord(
            id=document_id,
            source_type="local_file",
            source_path="/data/uploads/a.txt",
            file_extension=".txt",
            mime_type="text/plain",
            title="A",
            content_hash="hash",
            uploaded_by="u1",
        )
        repo = MagicMock()
        repo.get_document.return_value = document

        with patch("nexus_api.routers.documents.build_repository", return_value=repo):
            response = TestClient(app).post(
                f"/api/v1/documents/{document_id}/ack", headers={"X-User-Id": "u2"}
            )

        self.assertEqual(response.status_code, 403)
        repo.ack_document.assert_not_called()

    def test_ack_404_when_document_missing(self) -> None:
        repo = MagicMock()
        repo.get_document.return_value = None

        with patch("nexus_api.routers.documents.build_repository", return_value=repo):
            response = TestClient(app).post(f"/api/v1/documents/{uuid4()}/ack", headers={"X-User-Id": "u1"})

        self.assertEqual(response.status_code, 404)

    def test_ack_409_when_already_acked(self) -> None:
        document_id = uuid4()
        document = DocumentRecord(
            id=document_id,
            source_type="local_file",
            source_path="/data/uploads/a.txt",
            file_extension=".txt",
            mime_type="text/plain",
            title="A",
            content_hash="hash",
            uploaded_by="u1",
        )
        repo = MagicMock()
        repo.get_document.return_value = document
        repo.ack_document.side_effect = ValueError("document already acknowledged")

        with (
            patch("nexus_api.routers.documents.build_repository", return_value=repo),
            patch("nexus_api.routers.documents.build_vector_client"),
        ):
            response = TestClient(app).post(
                f"/api/v1/documents/{document_id}/ack", headers={"X-User-Id": "u1"}
            )

        self.assertEqual(response.status_code, 409)

    def test_admin_can_ack_anyones_document(self) -> None:
        document_id = uuid4()
        document = DocumentRecord(
            id=document_id,
            source_type="local_file",
            source_path="/data/uploads/a.txt",
            file_extension=".txt",
            mime_type="text/plain",
            title="A",
            content_hash="hash",
            uploaded_by="u1",
        )
        repo = MagicMock()
        repo.get_document.return_value = document
        repo.ack_document.return_value = (document.model_copy(update={"acked_by": "root"}), [])

        with (
            patch("nexus_api.routers.documents.build_repository", return_value=repo),
            patch("nexus_api.routers.documents.build_vector_client"),
        ):
            response = TestClient(app).post(f"/api/v1/documents/{document_id}/ack", headers=ADMIN_HEADERS)

        self.assertEqual(response.status_code, 200)

    def test_awaiting_ack_scoped_to_own_uploads_for_non_admin(self) -> None:
        repo = MagicMock()
        repo.list_documents_awaiting_ack.return_value = []

        with patch("nexus_api.routers.documents.build_repository", return_value=repo):
            response = TestClient(app).get(
                "/api/v1/documents/awaiting-ack", headers={"X-User-Id": "u1"}
            )

        self.assertEqual(response.status_code, 200)
        repo.list_documents_awaiting_ack.assert_called_once_with(uploaded_by="u1")

    def test_awaiting_ack_unscoped_for_admin(self) -> None:
        repo = MagicMock()
        repo.list_documents_awaiting_ack.return_value = []

        with patch("nexus_api.routers.documents.build_repository", return_value=repo):
            response = TestClient(app).get("/api/v1/documents/awaiting-ack", headers=ADMIN_HEADERS)

        self.assertEqual(response.status_code, 200)
        repo.list_documents_awaiting_ack.assert_called_once_with()


class JobStatusApiTest(unittest.TestCase):
    def test_get_job_returns_queue_position_when_queued(self) -> None:
        job = make_job(status=JobStatus.QUEUED)
        repo = MagicMock()
        repo.get_ingestion_job.return_value = job
        repo.queue_position.return_value = 3

        with patch("nexus_api.routers.documents.build_repository", return_value=repo):
            response = TestClient(app).get(f"/api/v1/jobs/{job.id}", headers=ADMIN_HEADERS)

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["queue_position"], 3)
        self.assertEqual(payload["status"], "queued")

    def test_get_job_omits_queue_position_when_not_queued(self) -> None:
        job = make_job(status=JobStatus.INDEXED)
        repo = MagicMock()
        repo.get_ingestion_job.return_value = job

        with patch("nexus_api.routers.documents.build_repository", return_value=repo):
            response = TestClient(app).get(f"/api/v1/jobs/{job.id}", headers=ADMIN_HEADERS)

        payload = response.json()
        self.assertIsNone(payload["queue_position"])
        repo.queue_position.assert_not_called()

    def test_get_job_404_when_missing(self) -> None:
        repo = MagicMock()
        repo.get_ingestion_job.return_value = None

        with patch("nexus_api.routers.documents.build_repository", return_value=repo):
            response = TestClient(app).get(f"/api/v1/jobs/{uuid4()}", headers=ADMIN_HEADERS)

        self.assertEqual(response.status_code, 404)

    def test_retry_job_success(self) -> None:
        job = make_job(status=JobStatus.QUEUED, attempt=0)
        repo = MagicMock()
        repo.get_ingestion_job.return_value = job
        repo.retry_job.return_value = job
        repo.queue_position.return_value = 1

        with patch("nexus_api.routers.documents.build_repository", return_value=repo):
            response = TestClient(app).post(f"/api/v1/jobs/{job.id}/retry", headers=ADMIN_HEADERS)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "queued")

    def test_retry_job_conflict_when_not_failed(self) -> None:
        job = make_job(status=JobStatus.FAILED)
        repo = MagicMock()
        repo.get_ingestion_job.return_value = job
        repo.retry_job.side_effect = ValueError("only failed jobs can be retried")

        with patch("nexus_api.routers.documents.build_repository", return_value=repo):
            response = TestClient(app).post(f"/api/v1/jobs/{uuid4()}/retry", headers=ADMIN_HEADERS)

        self.assertEqual(response.status_code, 409)

    def test_retry_job_404_when_missing(self) -> None:
        repo = MagicMock()
        repo.get_ingestion_job.return_value = None

        with patch("nexus_api.routers.documents.build_repository", return_value=repo):
            response = TestClient(app).post(f"/api/v1/jobs/{uuid4()}/retry", headers=ADMIN_HEADERS)

        self.assertEqual(response.status_code, 404)


if __name__ == "__main__":
    unittest.main()
