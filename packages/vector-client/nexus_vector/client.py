from __future__ import annotations

import logging
from typing import Any
from uuid import UUID

from qdrant_client import QdrantClient
from qdrant_client.models import Distance, FieldCondition, Filter, MatchAny, MatchValue, PointStruct, VectorParams

from nexus_shared.contracts import QdrantChunkPayload, SourceType

logger = logging.getLogger(__name__)


class NexusVectorClient:
    def __init__(
        self,
        host: str = "localhost",
        port: int = 6333,
        collection_name: str = "nexus_chunks",
        vector_size: int = 1024,
        url: str | None = None,
    ) -> None:
        self.collection_name = collection_name
        self.vector_size = vector_size
        import os
        qdrant_url = url or os.getenv("QDRANT_URL")
        if qdrant_url:
            self.client = QdrantClient(url=qdrant_url)
        else:
            self.client = QdrantClient(host=host, port=port)

    def ensure_collection(self) -> None:
        try:
            collections = self.client.get_collections().collections
            existing = {collection.name for collection in collections}
            if self.collection_name in existing:
                return
            self.client.create_collection(
                collection_name=self.collection_name,
                vectors_config=VectorParams(size=self.vector_size, distance=Distance.COSINE),
            )
        except Exception:
            logger.exception("failed to ensure Qdrant collection %s", self.collection_name)
            raise

    def upsert_chunks(self, points: list[tuple[UUID, list[float], QdrantChunkPayload]]) -> None:
        if not points:
            return
        self.ensure_collection()
        qdrant_points = [
            PointStruct(id=str(point_id), vector=vector, payload=payload.model_dump())
            for point_id, vector, payload in points
        ]
        try:
            self.client.upsert(collection_name=self.collection_name, points=qdrant_points)
        except Exception:
            logger.exception("failed to upsert %s chunks into Qdrant", len(qdrant_points))
            raise

    def set_payload(self, point_ids: list[UUID], payload: dict[str, Any]) -> None:
        """Metadata-only update (e.g. flipping `published`) -- no re-embedding needed."""
        if not point_ids:
            return
        self.ensure_collection()
        try:
            self.client.set_payload(
                collection_name=self.collection_name,
                payload=payload,
                points=[str(point_id) for point_id in point_ids],
            )
        except Exception:
            logger.exception("failed to set payload for %s points in %s", len(point_ids), self.collection_name)
            raise

    def search(
        self,
        vector: list[float],
        limit: int = 10,
        tags: list[str] | None = None,
        source_type: SourceType | None = None,
        workspace_ids: list[str] | None = None,
        require_published: bool = False,
    ) -> list[dict[str, Any]]:
        self.ensure_collection()
        query_filter = build_search_filter(
            tags=tags or [],
            source_type=source_type,
            workspace_ids=workspace_ids,
            require_published=require_published,
        )
        try:
            results = self.client.query_points(
                collection_name=self.collection_name,
                query=vector,
                limit=limit,
                query_filter=query_filter,
                with_payload=True,
            )
        except Exception:
            logger.exception("failed to search Qdrant collection %s", self.collection_name)
            raise
        return [
            {
                "id": point.id,
                "score": point.score,
                "payload": point.payload or {},
            }
            for point in results.points
        ]


def build_search_filter(
    tags: list[str],
    source_type: SourceType | None,
    workspace_ids: list[str] | None = None,
    require_published: bool = False,
) -> Filter | None:
    conditions: list[FieldCondition] = []
    if tags:
        conditions.append(FieldCondition(key="tags", match=MatchAny(any=tags)))
    if source_type is not None:
        conditions.append(FieldCondition(key="source_type", match=MatchValue(value=source_type.value)))
    if workspace_ids is not None:
        # Explicit empty list means "no workspace access" -- must match nothing, not everything.
        conditions.append(FieldCondition(key="workspace_id", match=MatchAny(any=workspace_ids)))
    if require_published:
        # Opt-in: the graph module's raw vector_client.search() calls use a
        # different collection/payload shape without a `published` field, so
        # this must never be applied unconditionally.
        conditions.append(FieldCondition(key="published", match=MatchValue(value=True)))
    if not conditions:
        return None
    return Filter(must=conditions)
