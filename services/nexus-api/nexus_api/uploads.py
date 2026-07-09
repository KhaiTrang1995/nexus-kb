from __future__ import annotations

import hashlib
import uuid
from pathlib import Path
from typing import BinaryIO
from uuid import UUID

from nexus_api.config import Settings
from nexus_document_parser.loader import SUPPORTED_EXTENSIONS
from nexus_document_parser.ports import MetadataRepository
from nexus_shared.contracts import DuplicateNotice, UploadJobSummary, UploadResponse


class UploadRejected(Exception):
    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class UploadedFile:
    """Transport-agnostic view over an incoming multipart file (decouples the
    service from FastAPI's UploadFile so it stays testable without an app)."""

    def __init__(self, filename: str, stream: BinaryIO) -> None:
        self.filename = filename
        self.stream = stream


class UploadService:
    def __init__(self, repository: MetadataRepository, settings: Settings) -> None:
        self.repository = repository
        self.settings = settings

    def accept(
        self,
        files: list[UploadedFile],
        uploaded_by: str,
        workspace_id: UUID,
        is_admin: bool,
        accessible_workspace_ids: list[str],
        confirm_version_of: UUID | None = None,
    ) -> UploadResponse:
        if len(files) == 0:
            raise UploadRejected("Chua chon file nao de upload.")
        if len(files) > self.settings.upload_max_files_per_batch:
            raise UploadRejected(
                f"Moi lan chi upload toi da {self.settings.upload_max_files_per_batch} file. "
                "Vui long bo bot va thu lai."
            )
        if confirm_version_of is not None and len(files) != 1:
            raise UploadRejected("confirm_version_of chi ap dung khi upload dung 1 file.")
        # workspace_id itself is authorized by the router (require_workspace_access,
        # fail-closed) before this is called; here we only need the extra check for
        # confirm_version_of, since that targets a *different*, possibly-inaccessible
        # document that only this service can look up.
        if confirm_version_of is not None:
            existing_document = self.repository.get_document(confirm_version_of)
            if existing_document is None:
                raise UploadRejected("Khong tim thay tai lieu de tao phien ban moi.")
            existing_workspace_id = (
                str(existing_document.workspace_id) if existing_document.workspace_id else None
            )
            if not is_admin and existing_workspace_id not in accessible_workspace_ids:
                raise UploadRejected("Ban khong co quyen tao phien ban cho tai lieu nay.")

        staging_dir = Path(self.settings.upload_staging_dir)
        staging_dir.mkdir(parents=True, exist_ok=True)
        max_bytes = self.settings.upload_max_file_size_mb * 1024 * 1024

        jobs: list[UploadJobSummary] = []
        rejected: list[str] = []
        duplicates: list[DuplicateNotice] = []

        for upload in files:
            extension = Path(upload.filename or "").suffix.lower()
            if extension not in SUPPORTED_EXTENSIONS:
                rejected.append(f"{upload.filename}: dinh dang khong duoc ho tro")
                continue

            content = upload.stream.read()
            if len(content) == 0:
                rejected.append(f"{upload.filename}: file rong")
                continue
            if len(content) > max_bytes:
                rejected.append(
                    f"{upload.filename}: vuot qua dung luong cho phep (toi da {self.settings.upload_max_file_size_mb}MB)"
                )
                continue

            raw_hash = hashlib.sha256(content).hexdigest()
            target_document_id = confirm_version_of

            if target_document_id is None:
                existing_job = self.repository.find_indexed_job_by_raw_hash(raw_hash)
                existing_document = (
                    self.repository.get_document(existing_job.document_id)
                    if existing_job is not None and existing_job.document_id is not None
                    else None
                )
                if existing_document is not None:
                    duplicates.append(
                        DuplicateNotice(
                            original_filename=upload.filename or "",
                            raw_content_hash=raw_hash,
                            existing_document_id=existing_document.id,
                            existing_document_title=existing_document.title,
                        )
                    )
                    continue

            staged_path = staging_dir / f"{uuid.uuid4()}{extension}"
            staged_path.write_bytes(content)

            job = self.repository.create_ingestion_job(
                source_path=str(staged_path.resolve()),
                original_filename=upload.filename or staged_path.name,
                file_extension=extension,
                uploaded_by=uploaded_by,
                workspace_id=workspace_id,
                max_attempts=self.settings.ingestion_job_max_attempts,
                raw_content_hash=raw_hash,
                target_document_id=target_document_id,
            )
            jobs.append(
                UploadJobSummary(job_id=job.id, original_filename=job.original_filename, status=job.status)
            )

        return UploadResponse(jobs=jobs, rejected=rejected, duplicates=duplicates)
