from __future__ import annotations

from datetime import datetime
from enum import StrEnum
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


class SearchResponse(BaseModel):
    query: str
    results: list[SearchResult]
