from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile

from nexus_api.ack import AckService
from nexus_api.auth.dependencies import get_current_user, require_workspace_access
from nexus_api.auth.models import AuthenticatedUser
from nexus_api.config import get_settings
from nexus_api.dependencies import build_repository, build_vector_client
from nexus_api.uploads import UploadedFile, UploadRejected, UploadService
from nexus_shared.contracts import (
    DocumentAckResponse,
    DocumentVersionListResponse,
    JobStatus,
    JobStatusResponse,
    PendingAckListResponse,
    UploadResponse,
)

router = APIRouter(tags=["documents"])


def _to_job_status_response(job, queue_position: int | None) -> JobStatusResponse:
    return JobStatusResponse(
        id=job.id,
        original_filename=job.original_filename,
        status=job.status,
        attempt=job.attempt,
        max_attempts=job.max_attempts,
        error_message=job.error_message,
        document_id=job.document_id,
        queue_position=queue_position,
        queued_at=job.queued_at,
        started_at=job.started_at,
        finished_at=job.finished_at,
    )


def _require_job_access(user: AuthenticatedUser, job) -> None:
    if user.is_admin:
        return
    if job.workspace_id is not None and str(job.workspace_id) in user.workspace_ids:
        return
    raise HTTPException(status_code=403, detail="No access to this job")


@router.post("/api/v1/documents", response_model=UploadResponse)
def upload_documents(
    workspace_id: UUID = Form(...),
    files: list[UploadFile] = File(...),
    confirm_version_of: UUID | None = Form(default=None),
    user: AuthenticatedUser = Depends(get_current_user),
) -> UploadResponse:
    require_workspace_access(user, workspace_id)
    service = UploadService(build_repository(), get_settings())
    uploaded_files = [UploadedFile(filename=f.filename or "", stream=f.file) for f in files]
    try:
        return service.accept(
            uploaded_files,
            uploaded_by=user.id,
            workspace_id=workspace_id,
            is_admin=user.is_admin,
            accessible_workspace_ids=user.workspace_ids,
            confirm_version_of=confirm_version_of,
        )
    except UploadRejected as exc:
        raise HTTPException(status_code=400, detail=exc.message) from None


@router.get("/api/v1/documents/{document_id}/versions", response_model=DocumentVersionListResponse)
def get_document_versions(
    document_id: UUID, user: AuthenticatedUser = Depends(get_current_user)
) -> DocumentVersionListResponse:
    repository = build_repository()
    versions = repository.list_document_versions(document_id)
    if not versions:
        raise HTTPException(status_code=404, detail="document not found")
    workspace_id = versions[0].workspace_id
    if not user.is_admin and (workspace_id is None or str(workspace_id) not in user.workspace_ids):
        raise HTTPException(status_code=403, detail="No access to this document")
    return DocumentVersionListResponse(document_id=document_id, versions=versions)


@router.get("/api/v1/documents/awaiting-ack", response_model=PendingAckListResponse)
def list_documents_awaiting_ack(
    user: AuthenticatedUser = Depends(get_current_user),
) -> PendingAckListResponse:
    repository = build_repository()
    if user.is_admin:
        documents = repository.list_documents_awaiting_ack()
    else:
        documents = repository.list_documents_awaiting_ack(uploaded_by=user.id)
    return PendingAckListResponse(documents=documents)


@router.post("/api/v1/documents/{document_id}/ack", response_model=DocumentAckResponse)
def ack_document(
    document_id: UUID, user: AuthenticatedUser = Depends(get_current_user)
) -> DocumentAckResponse:
    repository = build_repository()
    document = repository.get_document(document_id)
    if document is None:
        raise HTTPException(status_code=404, detail="document not found")
    if not user.is_admin and document.uploaded_by != user.id:
        raise HTTPException(status_code=403, detail="Only the uploader can acknowledge this document")

    service = AckService(repository, build_vector_client())
    try:
        return service.ack(document_id, actor_id=user.id)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from None


@router.get("/api/v1/jobs/{job_id}", response_model=JobStatusResponse)
def get_job(job_id: UUID, user: AuthenticatedUser = Depends(get_current_user)) -> JobStatusResponse:
    repository = build_repository()
    job = repository.get_ingestion_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="job not found")
    _require_job_access(user, job)
    position = repository.queue_position(job_id) if job.status == JobStatus.QUEUED else None
    return _to_job_status_response(job, position)


@router.post("/api/v1/jobs/{job_id}/retry", response_model=JobStatusResponse)
def retry_job(job_id: UUID, user: AuthenticatedUser = Depends(get_current_user)) -> JobStatusResponse:
    repository = build_repository()
    existing = repository.get_ingestion_job(job_id)
    if existing is None:
        raise HTTPException(status_code=404, detail="job not found")
    _require_job_access(user, existing)
    try:
        job = repository.retry_job(job_id)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from None
    position = repository.queue_position(job_id)
    return _to_job_status_response(job, position)
