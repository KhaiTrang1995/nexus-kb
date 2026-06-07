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
    ) -> None:
        self.collection_name = collection_name
        self.vector_size = vector_size
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

    def search(
        self,
        vector: list[float],
        limit: int = 10,
        tags: list[str] | None = None,
        source_type: SourceType | None = None,
    ) -> list[dict[str, Any]]:
        self.ensure_collection()
        query_filter = build_search_filter(tags=tags or [], source_type=source_type)
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


def build_search_filter(tags: list[str], source_type: SourceType | None) -> Filter | None:
    conditions: list[FieldCondition] = []
    if tags:
        conditions.append(FieldCondition(key="tags", match=MatchAny(any=tags)))
    if source_type is not None:
        conditions.append(FieldCondition(key="source_type", match=MatchValue(value=source_type.value)))
    if not conditions:
        return None
    return Filter(must=conditions)
