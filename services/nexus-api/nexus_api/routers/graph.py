from __future__ import annotations

import json
import logging
import os
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel
from qdrant_client.models import PointStruct

from nexus_api import tsx_bridge
from nexus_api.auth.dependencies import get_current_user, require_privileged
from nexus_api.auth.models import AuthenticatedUser
from nexus_api.config import get_settings
from nexus_api.dependencies import (
    build_embedding_provider,
    build_graph_repository,
    build_graph_vector_client,
    build_hyperedge_extractor,
    build_llm_gateway,
    build_repository,
    build_template_registry,
)
from nexus_document_parser.chunker import TextChunker
from nexus_graph_builder import GraphBuildService
from nexus_shared.contracts import (
    AuditStatus,
    GraphBuildResult,
    GraphEntityContextChunk,
    GraphEntityContextResponse,
    GraphEntityRecord,
    GraphIngestResponse,
    GraphSearchItem,
    GraphSearchResponse,
    GraphStatsResponse,
    GraphViewResponse,
    ParsedDocument,
    SourceType,
)

logger = logging.getLogger(__name__)

router = APIRouter(tags=["graph"])


class GraphIngestRequest(BaseModel):
    text: str
    source: str
    actor_id: str


def _validate_write_actor(actor_id: str | None) -> None:
    if not actor_id or actor_id.strip() in ("", "anonymous", "guest", "unauthorized"):
        raise HTTPException(status_code=403, detail="actor_id is unauthorized for graph writes")


@router.post("/api/v1/graph/build", response_model=GraphBuildResult)
def build_graph(
    limit: int = 100,
    user: AuthenticatedUser = Depends(get_current_user),
) -> GraphBuildResult:
    require_privileged(user)
    suggestions = tsx_bridge.intercept(
        action=f"Build knowledge graph from approved chunks (limit={limit})",
        context="nexus-kb graph builder -- entity/relationship extraction",
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


@router.get("/api/v1/graph/chunks/{chunk_id}", response_model=GraphBuildResult)
def graph_for_chunk(chunk_id: str) -> GraphBuildResult:
    from uuid import UUID
    return build_graph_repository().graph_for_chunk(UUID(chunk_id))


@router.get("/api/v1/graph/view", response_model=GraphViewResponse)
def graph_view(limit: int = 200, entity_type: str | None = None) -> GraphViewResponse:
    """Reads the already-built graph (no extraction) -- for the Explorer UI,
    which should not have to re-run a build just to look at the graph."""
    repository = build_graph_repository()
    entities = repository.list_entities(limit=limit, entity_type=entity_type)
    relationships = repository.list_relationships_among([entity.id for entity in entities])
    return GraphViewResponse(entities=entities, relationships=relationships)


@router.get("/api/v1/graph/entities/search", response_model=list[GraphEntityRecord])
def graph_entities_search(q: str, limit: int = 20) -> list[GraphEntityRecord]:
    if not q.strip():
        return []
    return build_graph_repository().search_entities(q, limit=limit)


@router.get("/api/v1/graph/entities/{entity_id}/neighbors", response_model=GraphViewResponse)
def graph_entity_neighbors(entity_id: str) -> GraphViewResponse:
    from uuid import UUID

    entities, relationships = build_graph_repository().get_entity_neighbors(UUID(entity_id))
    return GraphViewResponse(entities=entities, relationships=relationships)


@router.get("/api/v1/graph/entities/{entity_id}/context", response_model=GraphEntityContextResponse)
def graph_entity_context(entity_id: str) -> GraphEntityContextResponse:
    """Node-click panel content: the source chunk(s)/document(s) this entity
    was extracted from, so a user can jump from a graph node to its text."""
    from uuid import UUID

    graph_repository = build_graph_repository()
    entity = graph_repository.get_entity(UUID(entity_id))
    if entity is None:
        raise HTTPException(status_code=404, detail="entity not found")

    raw_chunk_ids = entity.provenance.get("chunk_id")
    chunk_id_values = raw_chunk_ids if isinstance(raw_chunk_ids, list) else ([raw_chunk_ids] if raw_chunk_ids else [])

    repository = build_repository()
    chunks: list[GraphEntityContextChunk] = []
    for raw_chunk_id in chunk_id_values:
        try:
            chunk_uuid = UUID(str(raw_chunk_id))
        except ValueError:
            continue
        row = repository.get_chunk_with_document(chunk_uuid)
        if row is None:
            continue
        chunks.append(
            GraphEntityContextChunk(
                chunk_id=row["chunk_id"],
                document_id=row["document_id"],
                document_title=row["title"],
                source_path=row["source_path"],
                content=row["content"],
            )
        )
    return GraphEntityContextResponse(entity=entity, chunks=chunks)


@router.post("/api/v1/graph/ingest", response_model=GraphIngestResponse)
def graph_ingest(request: GraphIngestRequest) -> GraphIngestResponse:
    _validate_write_actor(request.actor_id)

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

    embedding_provider = build_embedding_provider()
    chunk_texts = [c.content for c in chunks]

    points: list[PointStruct] = []
    if chunk_texts:
        vectors = embedding_provider.embed(chunk_texts)
        for chunk, vector in zip(chunks, vectors):
            point_id = uuid.uuid4()
            payload = {
                "text": chunk.content,
                "source": request.source,
                "chunk_index": chunk.chunk_index,
            }
            points.append(PointStruct(id=str(point_id), vector=vector, payload=payload))

        vector_client = build_graph_vector_client()
        vector_client.ensure_collection()
        vector_client.client.upsert(
            collection_name=vector_client.collection_name,
            points=points,
        )

    audit_event = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "actor_id": request.actor_id,
        "action": "GRAPH_WRITE",
        "status": "SUCCESS",
        "details": {
            "source": request.source,
            "chunk_count": len(points),
            "text_length": len(request.text),
        },
    }
    logger.info("AUDIT_EVENT: %s", json.dumps(audit_event))

    try:
        build_repository().record_audit_log(
            actor_id=request.actor_id,
            action="GRAPH_WRITE",
            status=AuditStatus.SUCCESS,
            details={"source": request.source, "chunk_count": len(points)},
        )
    except Exception:
        logger.warning("Failed to log graph ingest audit to SQL database, relying on JSON log")

    try:
        settings = get_settings()
        audit_dir = settings.audit_log_dir
        os.makedirs(audit_dir, exist_ok=True)
        with open(os.path.join(audit_dir, "audit_log.json"), "a", encoding="utf-8") as f:
            f.write(json.dumps(audit_event) + "\n")
    except Exception as e:
        logger.error("Failed to write to audit JSON file: %s", e)

    return GraphIngestResponse(status="ok", chunks_count=len(points))


@router.get("/api/v1/graph/search", response_model=GraphSearchResponse)
def graph_search(
    q: str,
    limit: int = 10,
    actor_id: str | None = Header(default=None, alias="X-Actor-Id"),
) -> GraphSearchResponse:
    if not actor_id:
        raise HTTPException(status_code=403, detail="actor_id header required")
    _validate_write_actor(actor_id)

    vector_client = build_graph_vector_client()
    embedding_provider = build_embedding_provider()

    query_vector = embedding_provider.embed([q])[0]
    results = vector_client.search(vector=query_vector, limit=limit)

    items: list[GraphSearchItem] = []
    for r in results:
        payload = r.get("payload") or {}
        items.append(GraphSearchItem(
            score=r.get("score"),
            source=payload.get("source", "unknown"),
            snippet=payload.get("text", ""),
        ))
    return GraphSearchResponse(results=items)


@router.get("/api/v1/graph/stats", response_model=GraphStatsResponse)
def graph_stats() -> GraphStatsResponse:
    try:
        vector_client = build_graph_vector_client()
        vector_client.ensure_collection()
        collection_info = vector_client.client.get_collection(
            collection_name=vector_client.collection_name
        )
        return GraphStatsResponse(node_count=collection_info.points_count)
    except Exception as e:
        logger.warning("Failed to get live node count from Qdrant: %s", e)
        return GraphStatsResponse(node_count=0, error=str(e))
