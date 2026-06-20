from __future__ import annotations

import logging
from functools import lru_cache
from pathlib import Path

from fastapi import FastAPI, Header, HTTPException

from nexus_api.audit import list_audit_records
from nexus_api.review import ReviewService, require_reviewer
from nexus_api.config import get_settings
from nexus_api.search import SearchService
from nexus_api import tsx_bridge
from nexus_graph_builder import GraphBuildService, SQLAlchemyGraphRepository
from nexus_shared.contracts import (
    AuditRecord,
    GraphBuildResult,
    IngestionRequest,
    IngestionResponse,
    ReviewActionRequest,
    ReviewActionResponse,
    ReviewItemRecord,
    SearchRequest,
    SearchResponse,
    AuditStatus,
    SourceType,
    ParsedDocument,
)
from nexus_document_parser.chunker import TextChunker
from nexus_document_parser.embedding import SentenceTransformerEmbeddingProvider
from nexus_document_parser.pipeline import IngestionPipeline
from nexus_document_parser.sqlalchemy_repository import SQLAlchemyMetadataRepository
from nexus_vector.client import NexusVectorClient
from pydantic import BaseModel
from typing import Optional

logger = logging.getLogger(__name__)

app = FastAPI(title="Nexus-KB API", version="0.3.0")


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


@lru_cache(maxsize=1)
def build_llm_gateway():
    """Return a configured LLMGateway when LLM_ENABLED=true, else None."""
    settings = get_settings()
    if not settings.llm_enabled:
        return None
    from nexus_llm_gateway.gateway import LLMGateway
    from nexus_llm_gateway.schemas import ModelRoute
    if settings.llm_provider == "ollama":
        from nexus_llm_gateway.providers import OllamaProvider
        provider = OllamaProvider(base_url=settings.llm_base_url)
    elif settings.llm_provider == "openai":
        from nexus_llm_gateway.providers import OpenAIProvider
        provider = OpenAIProvider(api_key=settings.llm_api_key, base_url=settings.llm_base_url)
    else:
        logger.warning("Unknown LLM_PROVIDER=%s — LLM extraction disabled", settings.llm_provider)
        return None
    route = ModelRoute(task_type="entity_extraction", provider=settings.llm_provider, model=settings.llm_model)
    default = ModelRoute(task_type="default", provider=settings.llm_provider, model=settings.llm_model)
    return LLMGateway(providers={settings.llm_provider: provider}, routes=[route], default_route=default)


@lru_cache(maxsize=1)
def build_template_registry():
    """Load domain templates from data/domain-templates/ if the directory exists."""
    templates_dir = Path(__file__).parents[3] / "data" / "domain-templates"
    if not templates_dir.exists():
        return None
    from nexus_graph_builder.domain_template import DomainTemplateRegistry
    return DomainTemplateRegistry(templates_dir)


@lru_cache(maxsize=1)
def build_hyperedge_extractor():
    """Return HyperedgeExtractor when LLM is enabled, else None."""
    gateway = build_llm_gateway()
    if gateway is None:
        return None
    from nexus_graph_builder.hyperedge_extractor import HyperedgeExtractor
    return HyperedgeExtractor(gateway=gateway)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "nexus-api", "version": "0.2.0"}


@app.post("/api/v1/ingest", response_model=IngestionResponse)
def ingest(request: IngestionRequest) -> IngestionResponse:
    # Intercept: get suggestions before write
    tsx_bridge.intercept(
        action=f"Ingest document from {request.source_path}",
        context=f"source_type={request.source_type}",
    )

    embedding_provider = build_embedding_provider()
    pipeline = IngestionPipeline(
        repository=build_repository(),
        vector_client=build_vector_client(),
        embedding_provider=embedding_provider,
    )
    result = pipeline.ingest(request.source_path, request.source_type)

    # Save experience: record what was ingested
    tsx_bridge.save_experience(
        title=f"Ingested: {request.source_path}",
        description=(
            f"Source: {request.source_path} | Type: {request.source_type}\n"
            f"Chunks: {getattr(result, 'chunk_count', '?')} | "
            f"Status: {getattr(result, 'status', 'ok')}"
        ),
        tags=["nexus-kb", "ingest", request.source_type],
    )
    return result


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
    # Intercept: get suggestions before graph build
    suggestions = tsx_bridge.intercept(
        action=f"Build knowledge graph from approved chunks (limit={limit})",
        context="nexus-kb graph builder — entity/relationship extraction",
    )
    if suggestions:
        logger.info("TSX suggestions for graph build: %s", [s.get("title") for s in suggestions[:3]])

    settings = get_settings()
    service = GraphBuildService(
        build_repository(),
        build_graph_repository(),
        llm_gateway=build_llm_gateway(),
        template_registry=build_template_registry() if settings.llm_enabled else None,
        domain=settings.graph_domain if settings.llm_enabled else None,
        hyperedge_extractor=build_hyperedge_extractor(),
    )
    result = service.build_from_approved_chunks(limit=limit)

    # Save experience with graph build outcome
    entities = getattr(result, "entity_count", None) or len(getattr(result, "entities", []))
    edges = getattr(result, "relationship_count", None) or len(getattr(result, "relationships", []))
    tsx_bridge.save_experience(
        title=f"Knowledge graph built: {entities} entities, {edges} edges",
        description=(
            f"Graph build completed.\n"
            f"Entities extracted: {entities}\n"
            f"Relationships extracted: {edges}\n"
            f"Chunk limit: {limit}"
        ),
        tags=["nexus-kb", "graph-build", "knowledge-graph"],
        category="nexus-kb",
    )
    return result


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


# ── TechSphereX deliberation proxy ──────────────────────────────────────────

class DeliberateRequest(BaseModel):
    topic: str
    context: str = ""
    from_cli: str = "nexus-kb"
    preferred_consultants: Optional[list[str]] = None


class DeliberateResponse(BaseModel):
    deliberation_id: Optional[str]
    status: str


@app.post("/api/v1/deliberate", response_model=DeliberateResponse, status_code=202)
def deliberate(request: DeliberateRequest) -> DeliberateResponse:
    """
    Trigger a multi-CLI deliberation via TechSphereX engine.
    Visible in Fleet Monitor → Council Room.
    """
    d_id = tsx_bridge.deliberate(
        topic=request.topic,
        context=request.context,
        from_cli=request.from_cli,
        preferred_consultants=request.preferred_consultants,
    )
    return DeliberateResponse(
        deliberation_id=d_id,
        status="accepted" if d_id else "engine_unavailable",
    )


# ── Knowledge Graph Custom Endpoints ────────────────────────────────────────

class GraphIngestRequest(BaseModel):
    text: str
    source: str
    actor_id: str


def validate_write_actor(actor_id: str | None) -> None:
    if not actor_id or actor_id.strip() in ("", "anonymous", "guest", "unauthorized"):
        raise HTTPException(status_code=403, detail="actor_id is unauthorized for graph writes")


@lru_cache(maxsize=1)
def build_graph_vector_client() -> NexusVectorClient:
    settings = get_settings()
    return NexusVectorClient(
        host=settings.qdrant_host,
        port=settings.qdrant_port,
        collection_name="nexus_graph",
        vector_size=settings.embedding_dimension,
    )


@app.post("/api/v1/graph/ingest")
def graph_ingest(request: GraphIngestRequest) -> dict:
    # 1. RBAC: validate actor_id before any write
    validate_write_actor(request.actor_id)

    # 2. Chunk text using TextChunker
    doc = ParsedDocument(
        source_type=SourceType.LOCAL_FILE,
        source_path=request.source,
        file_extension="txt",
        mime_type="text/plain",
        title=request.source,
        content=request.text,
        content_hash="",
    )
    chunker = TextChunker()
    chunks = chunker.chunk_document(doc)

    # 3. Embed chunks via sentence-transformers
    embedding_provider = build_embedding_provider()
    chunk_texts = [c.content for c in chunks]
    
    import uuid
    from qdrant_client.models import PointStruct
    
    points = []
    if chunk_texts:
        vectors = embedding_provider.embed(chunk_texts)
        for chunk, vector in zip(chunks, vectors):
            point_id = uuid.uuid4()
            payload = {
                "text": chunk.content,
                "source": request.source,
                "chunk_index": chunk.chunk_index
            }
            points.append(PointStruct(id=str(point_id), vector=vector, payload=payload))
            
        # 4. Store in Qdrant collection "nexus_graph"
        vector_client = build_graph_vector_client()
        vector_client.ensure_collection()
        vector_client.client.upsert(
            collection_name=vector_client.collection_name,
            points=points
        )

    # 5. Emit audit event (log to structured JSON)
    import json
    import os
    from datetime import datetime, timezone
    
    audit_event = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "actor_id": request.actor_id,
        "action": "GRAPH_WRITE",
        "status": "SUCCESS",
        "details": {
            "source": request.source,
            "chunk_count": len(points),
            "text_length": len(request.text),
        }
    }
    logger.info("AUDIT_EVENT: %s", json.dumps(audit_event))
    
    # Try recording in the database repository as well
    try:
        build_repository().record_audit_log(
            actor_id=request.actor_id,
            action="GRAPH_WRITE",
            status=AuditStatus.SUCCESS,
            details={"source": request.source, "chunk_count": len(points)},
        )
    except Exception:
        logger.warning("Failed to log graph ingest audit to SQL database, relying on JSON log")

    # Also log to structured JSON file
    try:
        audit_dir = "D:/Github/nexus-kb/data"
        os.makedirs(audit_dir, exist_ok=True)
        with open(os.path.join(audit_dir, "audit_log.json"), "a", encoding="utf-8") as f:
            f.write(json.dumps(audit_event) + "\n")
    except Exception as e:
        logger.error("Failed to write to audit JSON file: %s", e)

    return {"status": "ok", "chunks_count": len(points)}


@app.get("/api/v1/graph/search")
def graph_search(
    q: str,
    limit: int = 10,
    actor_id: str | None = Header(default=None, alias="X-Actor-Id"),
) -> dict:
    # RBAC stub validation: check actor_id header
    if not actor_id:
        raise HTTPException(status_code=403, detail="actor_id header required")
    validate_write_actor(actor_id)

    vector_client = build_graph_vector_client()
    embedding_provider = build_embedding_provider()
    
    query_vector = embedding_provider.embed([q])[0]
    results = vector_client.search(
        vector=query_vector,
        limit=limit,
    )
    
    items = []
    for r in results:
        payload = r.get("payload") or {}
        items.append({
            "score": r.get("score"),
            "source": payload.get("source", "unknown"),
            "snippet": payload.get("text", "")
        })
    return {"results": items}


@app.get("/api/v1/graph/stats")
def graph_stats() -> dict:
    try:
        vector_client = build_graph_vector_client()
        vector_client.ensure_collection()
        collection_info = vector_client.client.get_collection(
            collection_name=vector_client.collection_name
        )
        return {"node_count": collection_info.points_count}
    except Exception as e:
        logger.warning("Failed to get live node count from Qdrant: %s", e)
        return {"node_count": 0, "error": str(e)}
