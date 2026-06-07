from __future__ import annotations

from functools import lru_cache

from fastapi import FastAPI, Header

from nexus_api.audit import list_audit_records
from nexus_api.review import ReviewService, require_reviewer
from nexus_api.config import get_settings
from nexus_api.search import SearchService
from nexus_graph_builder import GraphBuildService, SQLAlchemyGraphRepository
from nexus_shared.contracts import AuditRecord, GraphBuildResult, IngestionRequest, IngestionResponse, ReviewActionRequest, ReviewActionResponse, ReviewItemRecord, SearchRequest, SearchResponse
from nexus_document_parser.embedding import SentenceTransformerEmbeddingProvider
from nexus_document_parser.pipeline import IngestionPipeline
from nexus_document_parser.sqlalchemy_repository import SQLAlchemyMetadataRepository
from nexus_vector.client import NexusVectorClient

app = FastAPI(title="Nexus-KB API", version="0.1.0")


@lru_cache(maxsize=1)
def build_repository() -> SQLAlchemyMetadataRepository:
    settings = get_settings()
    return SQLAlchemyMetadataRepository(settings.postgres_dsn)


@lru_cache(maxsize=1)
def build_vector_client() -> NexusVectorClient:
    settings = get_settings()
    return NexusVectorClient(
        host=settings.qdrant_host,
        port=settings.qdrant_port,
        collection_name=settings.qdrant_collection,
        vector_size=settings.embedding_dimension,
    )


@lru_cache(maxsize=1)
def build_embedding_provider() -> SentenceTransformerEmbeddingProvider:
    settings = get_settings()
    return SentenceTransformerEmbeddingProvider(settings.embedding_model)


@lru_cache(maxsize=1)
def build_graph_repository() -> SQLAlchemyGraphRepository:
    settings = get_settings()
    return SQLAlchemyGraphRepository(settings.postgres_dsn)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "nexus-api"}


@app.post("/api/v1/ingest", response_model=IngestionResponse)
def ingest(request: IngestionRequest) -> IngestionResponse:
    embedding_provider = build_embedding_provider()
    pipeline = IngestionPipeline(
        repository=build_repository(),
        vector_client=build_vector_client(),
        embedding_provider=embedding_provider,
    )
    return pipeline.ingest(request.source_path, request.source_type)


@app.post("/api/v1/search", response_model=SearchResponse)
def search(request: SearchRequest) -> SearchResponse:
    embedding_provider = build_embedding_provider()
    service = SearchService(
        repository=build_repository(),
        vector_client=build_vector_client(),
        embedding_provider=embedding_provider,
        graph_repository=build_graph_repository(),
    )
    return service.search(request)


@app.post("/api/v1/graph/build", response_model=GraphBuildResult)
def build_graph(limit: int = 100) -> GraphBuildResult:
    service = GraphBuildService(build_repository(), build_graph_repository())
    return service.build_from_approved_chunks(limit=limit)


@app.get("/api/v1/graph/chunks/{chunk_id}", response_model=GraphBuildResult)
def graph_for_chunk(chunk_id: str) -> GraphBuildResult:
    from uuid import UUID

    return build_graph_repository().graph_for_chunk(UUID(chunk_id))


@app.get("/api/v1/audit", response_model=list[AuditRecord])
def audit(
    limit: int = 50,
    offset: int = 0,
    action_filter: str | None = None,
    actor_filter: str | None = None,
) -> list[AuditRecord]:
    return list_audit_records(build_repository(), limit, offset, action_filter, actor_filter)


@app.get("/api/v1/review/queue", response_model=list[ReviewItemRecord])
def review_queue(
    limit: int = 50,
    offset: int = 0,
    min_confidence: float | None = None,
    x_user_role: str | None = Header(default=None),
) -> list[ReviewItemRecord]:
    require_reviewer(x_user_role)
    service = ReviewService(build_repository(), build_vector_client(), build_embedding_provider())
    return service.list_queue(limit=limit, offset=offset, min_confidence=min_confidence)


@app.post("/api/v1/review/action", response_model=ReviewActionResponse)
def review_action(
    request: ReviewActionRequest,
    x_user_role: str | None = Header(default=None),
    x_user_id: str | None = Header(default=None),
) -> ReviewActionResponse:
    require_reviewer(x_user_role)
    service = ReviewService(build_repository(), build_vector_client(), build_embedding_provider())
    return service.apply_action(request, reviewer_id=x_user_id or "anonymous-reviewer")
