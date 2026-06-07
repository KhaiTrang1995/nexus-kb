from __future__ import annotations

from functools import lru_cache

from fastapi import FastAPI

from nexus_api.config import get_settings
from nexus_api.search import SearchService
from nexus_shared.contracts import IngestionRequest, IngestionResponse, SearchRequest, SearchResponse
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
    )
    return service.search(request)
