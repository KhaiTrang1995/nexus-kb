from __future__ import annotations

import re
from uuid import UUID

from nexus_shared.contracts import AuditStatus, GraphBuildResult, SearchRequest, SearchResponse, SearchResult, SourceType
from nexus_document_parser.embedding import EmbeddingProvider
from nexus_document_parser.ports import MetadataRepository
from nexus_vector.client import NexusVectorClient


class SearchService:
    def __init__(
        self,
        repository: MetadataRepository,
        vector_client: NexusVectorClient,
        embedding_provider: EmbeddingProvider,
        graph_repository=None,
    ) -> None:
        self.repository = repository
        self.vector_client = vector_client
        self.embedding_provider = embedding_provider
        self.graph_repository = graph_repository

    def search(self, request: SearchRequest) -> SearchResponse:
        self.repository.record_audit_log(
            actor_id="system:search",
            action="SEARCH_QUERY",
            status=AuditStatus.SUCCESS,
            details={"query": request.query, "limit": request.limit, "tags": request.tags},
        )
        query_vector = self.embedding_provider.embed([request.query])[0]
        vector_limit = min(max(request.limit * 3, request.limit), 50)
        vector_results = self.vector_client.search(
            vector=query_vector,
            limit=vector_limit,
            tags=request.tags,
            source_type=request.source_type,
        )
        results: list[SearchResult] = []
        for item in vector_results:
            payload = item["payload"]
            chunk_id = UUID(str(payload["chunk_id"]))
            row = self.repository.get_chunk_with_document(chunk_id)
            if row is None:
                continue
            metadata = dict(row.get("chunk_metadata") or {})
            graph = self._graph_for_chunk(row["chunk_id"])
            vector_score = float(item["score"])
            rank_score = rerank_score(
                query=request.query,
                vector_score=vector_score,
                content=row["content"],
                title=row["title"],
                tags=list(row["tags"] or []),
                heading_path=list(metadata.get("heading_path") or []),
            )
            results.append(
                SearchResult(
                    score=rank_score,
                    vector_score=vector_score,
                    rank_score=rank_score,
                    chunk_id=row["chunk_id"],
                    document_id=row["document_id"],
                    title=row["title"],
                    source_path=row["source_path"],
                    file_extension=row["file_extension"],
                    mime_type=row["mime_type"],
                    source_type=SourceType(row["source_type"]),
                    chunk_index=row["chunk_index"],
                    content=row["content"],
                    snippet=build_snippet(row["content"], request.query),
                    metadata=metadata,
                    heading_path=list(metadata.get("heading_path") or []),
                    section_title=metadata.get("section_title"),
                    tags=list(row["tags"] or []),
                    wikilinks=list(row["wikilinks"] or []),
                    frontmatter=dict(row["frontmatter"] or {}),
                    graph_entities=graph.entities,
                    graph_relationships=graph.relationships,
                )
            )
        results.sort(key=lambda result: result.rank_score, reverse=True)
        return SearchResponse(query=request.query, results=results[: request.limit])

    def _graph_for_chunk(self, chunk_id: UUID) -> GraphBuildResult:
        if self.graph_repository is None or not hasattr(self.graph_repository, "graph_for_chunk"):
            return GraphBuildResult(entities=[], relationships=[])
        return self.graph_repository.graph_for_chunk(chunk_id)


def query_terms(query: str) -> list[str]:
    return [term.lower() for term in re.findall(r"[\w\-]+", query) if len(term) > 1]


def rerank_score(
    query: str,
    vector_score: float,
    content: str,
    title: str,
    tags: list[str],
    heading_path: list[str],
) -> float:
    terms = query_terms(query)
    if not terms:
        return vector_score

    content_text = content.lower()
    title_text = title.lower()
    tag_text = " ".join(tags).lower()
    heading_text = " ".join(heading_path).lower()

    content_hits = sum(1 for term in terms if term in content_text)
    title_hits = sum(1 for term in terms if term in title_text)
    tag_hits = sum(1 for term in terms if term in tag_text)
    heading_hits = sum(1 for term in terms if term in heading_text)
    lexical_ratio = content_hits / len(terms)

    return (
        vector_score
        + lexical_ratio * 0.12
        + title_hits * 0.04
        + heading_hits * 0.035
        + tag_hits * 0.025
    )


def build_snippet(content: str, query: str, max_chars: int = 260) -> str:
    terms = query_terms(query)
    lowered = content.lower()
    first_hit = min((lowered.find(term) for term in terms if term in lowered), default=-1)
    if first_hit < 0:
        return content[:max_chars].strip()

    start = max(first_hit - max_chars // 3, 0)
    end = min(start + max_chars, len(content))
    snippet = content[start:end].strip()
    if start > 0:
        snippet = f"...{snippet}"
    if end < len(content):
        snippet = f"{snippet}..."
    return snippet
