from __future__ import annotations

from nexus_graph_builder.builder import GraphBuilder
from nexus_shared.contracts import GraphBuildResult, GraphChunkInput


class GraphBuildService:
    def __init__(self, metadata_repository, graph_repository) -> None:
        self.metadata_repository = metadata_repository
        self.graph_repository = graph_repository

    def build_from_approved_chunks(self, limit: int = 100) -> GraphBuildResult:
        chunks: list[GraphChunkInput] = self.metadata_repository.list_approved_graph_chunks(limit=limit)
        return GraphBuilder(self.graph_repository).build_from_chunks(chunks)
