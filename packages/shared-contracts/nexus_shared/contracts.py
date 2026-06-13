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
    source_path: str
    source_type: SourceType = SourceType.LOCAL_FILE


class IngestionResponse(BaseModel):
    run_id: UUID
    status: IngestionStatus
    documents_seen: int
    documents_indexed: int
    chunks_indexed: int
    error_message: str | None = None


class SearchRequest(BaseModel):
    query: str
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


class SearchResponse(BaseModel):
    query: str
    results: list[SearchResult]


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


class GraphBuildResult(BaseModel):
    entities: list[GraphEntityRecord]
    relationships: list[GraphRelationshipRecord]


SearchResult.model_rebuild()
