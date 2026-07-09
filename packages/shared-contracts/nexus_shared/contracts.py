from __future__ import annotations

from datetime import datetime
try:
    from enum import StrEnum
except ImportError:
    from enum import Enum
    class StrEnum(str, Enum):
        pass

from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class SourceType(StrEnum):
    LOCAL_FILE = "local_file"
    OBSIDIAN = "obsidian"


class IngestionStatus(StrEnum):
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class AuditStatus(StrEnum):
    SUCCESS = "SUCCESS"
    FAILURE = "FAILURE"
    DENIED = "DENIED"


class ReviewStatus(StrEnum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    MODIFIED = "MODIFIED"


class ReviewAction(StrEnum):
    APPROVE = "APPROVE"
    REJECT = "REJECT"
    MODIFY = "MODIFY"


class ParsedDocument(BaseModel):
    source_type: SourceType
    source_path: str
    file_extension: str
    mime_type: str
    title: str
    content: str
    content_hash: str
    frontmatter: dict[str, Any] = Field(default_factory=dict)
    tags: list[str] = Field(default_factory=list)
    wikilinks: list[str] = Field(default_factory=list)


class DocumentRecord(BaseModel):
    id: UUID
    source_type: SourceType
    source_path: str
    file_extension: str
    mime_type: str
    title: str
    content_hash: str
    frontmatter: dict[str, Any] = Field(default_factory=dict)
    tags: list[str] = Field(default_factory=list)
    wikilinks: list[str] = Field(default_factory=list)
    current_version: int = 1
    workspace_id: UUID | None = None
    uploaded_by: str | None = None
    acked_by: str | None = None
    acked_at: datetime | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


class ChunkRecord(BaseModel):
    id: UUID
    document_id: UUID
    chunk_index: int
    content: str
    content_hash: str
    token_count: int
    metadata: dict[str, Any] = Field(default_factory=dict)
    qdrant_point_id: UUID
    embedding_model: str
    created_at: datetime | None = None


class ChunkCandidate(BaseModel):
    chunk_index: int
    content: str
    content_hash: str
    token_count: int
    metadata: dict[str, Any] = Field(default_factory=dict)


class QdrantChunkPayload(BaseModel):
    document_id: str
    chunk_id: str
    source_type: str
    source_path: str
    file_extension: str
    mime_type: str
    title: str
    tags: list[str] = Field(default_factory=list)
    wikilinks: list[str] = Field(default_factory=list)
    frontmatter: dict[str, Any] = Field(default_factory=dict)
    chunk_index: int
    heading_path: list[str] = Field(default_factory=list)
    section_title: str | None = None
    workspace_id: str | None = None
    published: bool = False


class WorkspaceRecord(BaseModel):
    id: UUID
    name: str
    slug: str
    created_at: datetime | None = None


class WorkspaceMemberRecord(BaseModel):
    workspace_id: UUID
    user_id: str
    created_at: datetime | None = None


class WorkspaceCreateRequest(BaseModel):
    name: str = Field(max_length=200)
    slug: str = Field(max_length=64)


class WorkspaceMemberAddRequest(BaseModel):
    user_id: str = Field(max_length=128)


class WorkspaceListResponse(BaseModel):
    workspaces: list[WorkspaceRecord]


class WorkspaceMemberListResponse(BaseModel):
    workspace_id: UUID
    members: list[WorkspaceMemberRecord]


class JobStatus(StrEnum):
    QUEUED = "queued"
    EXTRACTING = "extracting"
    INDEXED = "indexed"
    FAILED = "failed"


class IngestionJobRecord(BaseModel):
    id: UUID
    source_path: str
    original_filename: str
    file_extension: str
    uploaded_by: str
    workspace_id: UUID
    status: JobStatus
    attempt: int = 0
    max_attempts: int = 3
    error_message: str | None = None
    document_id: UUID | None = None
    run_id: UUID | None = None
    raw_content_hash: str | None = None
    target_document_id: UUID | None = None
    sync_run_id: UUID | None = None
    queued_at: datetime | None = None
    started_at: datetime | None = None
    finished_at: datetime | None = None


class SyncRunStatus(StrEnum):
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class SyncRunRecord(BaseModel):
    id: UUID
    space_key: str
    workspace_id: UUID
    status: SyncRunStatus
    actor_id: str
    pages_seen: int = 0
    pages_indexed: int = 0
    error_message: str | None = None
    started_at: datetime | None = None
    finished_at: datetime | None = None


class SyncRunTriggerRequest(BaseModel):
    space_key: str = Field(max_length=200)
    workspace_id: UUID


class SyncRunListResponse(BaseModel):
    sync_runs: list[SyncRunRecord]


class JobStatusResponse(BaseModel):
    id: UUID
    original_filename: str
    status: JobStatus
    attempt: int
    max_attempts: int
    error_message: str | None = None
    document_id: UUID | None = None
    queue_position: int | None = None
    queued_at: datetime | None = None
    started_at: datetime | None = None
    finished_at: datetime | None = None


class UploadJobSummary(BaseModel):
    job_id: UUID
    original_filename: str
    status: JobStatus


class DuplicateNotice(BaseModel):
    original_filename: str
    raw_content_hash: str
    existing_document_id: UUID
    existing_document_title: str


class UploadResponse(BaseModel):
    jobs: list[UploadJobSummary]
    rejected: list[str] = Field(default_factory=list)
    duplicates: list[DuplicateNotice] = Field(default_factory=list)


class DocumentVersionRecord(BaseModel):
    document_id: UUID
    workspace_id: UUID | None = None
    version_number: int
    title: str
    content_hash: str
    file_extension: str
    mime_type: str
    source_path: str
    uploaded_by: str | None = None
    acked_by: str | None = None
    acked_at: datetime | None = None
    is_current: bool
    created_at: datetime | None = None


class DocumentVersionListResponse(BaseModel):
    document_id: UUID
    versions: list[DocumentVersionRecord]


class DocumentAckResponse(BaseModel):
    document_id: UUID
    acked_by: str
    acked_at: datetime | None = None


class PendingAckListResponse(BaseModel):
    documents: list[DocumentRecord]


class IngestionRunRecord(BaseModel):
    id: UUID
    source_path: str
    status: IngestionStatus
    documents_seen: int = 0
    documents_indexed: int = 0
    chunks_indexed: int = 0
    error_message: str | None = None
    started_at: datetime | None = None
    finished_at: datetime | None = None


class IngestionRequest(BaseModel):
    source_path: str = Field(max_length=1024)
    source_type: SourceType = SourceType.LOCAL_FILE


class IngestionResponse(BaseModel):
    run_id: UUID
    status: IngestionStatus
    documents_seen: int
    documents_indexed: int
    chunks_indexed: int
    error_message: str | None = None


class SearchRequest(BaseModel):
    query: str = Field(max_length=500)
    limit: int = Field(default=10, ge=1, le=50)
    tags: list[str] = Field(default_factory=list)
    source_type: SourceType | None = None


class SearchResult(BaseModel):
    score: float
    vector_score: float
    rank_score: float
    chunk_id: UUID
    document_id: UUID
    title: str
    source_path: str
    file_extension: str
    mime_type: str
    source_type: SourceType
    chunk_index: int
    content: str
    snippet: str
    metadata: dict[str, Any] = Field(default_factory=dict)
    heading_path: list[str] = Field(default_factory=list)
    section_title: str | None = None
    tags: list[str] = Field(default_factory=list)
    wikilinks: list[str] = Field(default_factory=list)
    frontmatter: dict[str, Any] = Field(default_factory=dict)
    graph_entities: list["GraphEntityRecord"] = Field(default_factory=list)
    graph_relationships: list["GraphRelationshipRecord"] = Field(default_factory=list)
    document_version: int | None = None


class SearchResponse(BaseModel):
    query: str
    results: list[SearchResult]


class ChatRequest(BaseModel):
    query: str = Field(max_length=2000)
    limit: int = Field(default=5, ge=1, le=20)


class ChatCitation(BaseModel):
    chunk_id: UUID
    document_id: UUID
    title: str
    document_version: int | None = None
    snippet: str


class ChatResponse(BaseModel):
    answer: str
    citations: list[ChatCitation] = Field(default_factory=list)


class AuditRecord(BaseModel):
    id: UUID
    actor_id: str
    action: str
    status: AuditStatus
    resource_id: UUID | None = None
    details: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime | None = None


class ReviewItemRecord(BaseModel):
    id: UUID
    run_id: UUID
    source_path: str
    content: str
    confidence: float = Field(ge=0.0, le=1.0)
    status: ReviewStatus = ReviewStatus.PENDING
    payload: dict[str, Any] = Field(default_factory=dict)
    reviewer_id: str | None = None
    reviewed_at: datetime | None = None
    created_at: datetime | None = None


class ReviewActionRequest(BaseModel):
    item_id: UUID
    action: ReviewAction
    modified_content: str | None = None
    modified_payload: dict[str, Any] | None = None


class ReviewActionResponse(BaseModel):
    item_id: UUID
    status: ReviewStatus


class GraphChunkInput(BaseModel):
    chunk_id: UUID
    document_id: UUID
    content: str
    metadata: dict[str, Any] = Field(default_factory=dict)
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    wikilinks: list[str] = Field(default_factory=list)


class GraphEntityCandidate(BaseModel):
    name: str
    entity_type: str = "TERM"
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    provenance: dict[str, Any] = Field(default_factory=dict)


class GraphRelationshipCandidate(BaseModel):
    source_name: str
    target_name: str
    relationship_type: str = "RELATED_TO"
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    provenance: dict[str, Any] = Field(default_factory=dict)


class GraphEntityRecord(BaseModel):
    id: UUID
    name: str
    normalized_name: str
    entity_type: str
    confidence: float
    provenance: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime | None = None
    updated_at: datetime | None = None


class GraphRelationshipRecord(BaseModel):
    id: UUID
    source_entity_id: UUID
    target_entity_id: UUID
    relationship_type: str
    confidence: float
    provenance: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime | None = None
    updated_at: datetime | None = None


class HyperedgeCandidate(BaseModel):
    """An n-ary relationship that connects 3 or more entities simultaneously."""
    entity_names: list[str]           # 3+ entity names involved in this fact
    relationship_type: str = "INVOLVES"
    label: str = ""                   # human-readable description of the n-ary fact
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    provenance: dict[str, Any] = Field(default_factory=dict)


class HyperedgeRecord(BaseModel):
    id: UUID
    entity_ids: list[UUID]
    relationship_type: str
    label: str = ""
    confidence: float
    provenance: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime | None = None


class GraphBuildResult(BaseModel):
    entities: list[GraphEntityRecord]
    relationships: list[GraphRelationshipRecord]
    hyperedges: list[HyperedgeRecord] = Field(default_factory=list)


class GraphIngestResponse(BaseModel):
    status: str
    chunks_count: int


class GraphSearchItem(BaseModel):
    score: float | None = None
    source: str
    snippet: str


class GraphSearchResponse(BaseModel):
    results: list[GraphSearchItem]


class GraphStatsResponse(BaseModel):
    node_count: int
    error: str | None = None


class GraphViewResponse(BaseModel):
    entities: list["GraphEntityRecord"]
    relationships: list["GraphRelationshipRecord"]


class GraphEntityContextChunk(BaseModel):
    chunk_id: UUID
    document_id: UUID
    document_title: str
    source_path: str
    content: str


class GraphEntityContextResponse(BaseModel):
    entity: "GraphEntityRecord"
    chunks: list[GraphEntityContextChunk] = Field(default_factory=list)


SearchResult.model_rebuild()
