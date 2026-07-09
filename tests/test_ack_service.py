from __future__ import annotations

import unittest
from datetime import datetime, timezone
from unittest.mock import MagicMock
from uuid import uuid4

from tests import _paths  # noqa: F401

from nexus_api.ack import AckService
from nexus_shared.contracts import DocumentRecord


class AckServiceTest(unittest.TestCase):
    def test_ack_flips_qdrant_payload_and_records_audit(self) -> None:
        document_id = uuid4()
        chunk_ids = [uuid4(), uuid4()]
        acked_at = datetime.now(timezone.utc)
        document = DocumentRecord(
            id=document_id,
            source_type="local_file",
            source_path="/data/uploads/a.txt",
            file_extension=".txt",
            mime_type="text/plain",
            title="A",
            content_hash="hash",
            acked_by="u1",
            acked_at=acked_at,
        )
        repository = MagicMock()
        repository.ack_document.return_value = (document, chunk_ids)
        vector_client = MagicMock()

        service = AckService(repository, vector_client)
        response = service.ack(document_id, actor_id="u1")

        self.assertEqual(response.document_id, document_id)
        self.assertEqual(response.acked_by, "u1")
        vector_client.set_payload.assert_called_once_with(chunk_ids, {"published": True})
        repository.record_audit_log.assert_called_once()
        _, kwargs = repository.record_audit_log.call_args
        self.assertEqual(kwargs["action"], "DOCUMENT_ACK")
        self.assertEqual(kwargs["details"]["chunk_count"], 2)

    def test_ack_propagates_already_acked_error_without_touching_vector_client(self) -> None:
        repository = MagicMock()
        repository.ack_document.side_effect = ValueError("document already acknowledged: x")
        vector_client = MagicMock()
        service = AckService(repository, vector_client)

        with self.assertRaises(ValueError):
            service.ack(uuid4(), actor_id="u1")

        vector_client.set_payload.assert_not_called()


if __name__ == "__main__":
    unittest.main()
