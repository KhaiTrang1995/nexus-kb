from __future__ import annotations

from typing import TYPE_CHECKING

from nexus_graph_builder.builder import GraphBuilder
from nexus_graph_builder.extractor import LLMEntityExtractor
from nexus_shared.contracts import GraphBuildResult, GraphChunkInput

if TYPE_CHECKING:
    from nexus_graph_builder.domain_template import DomainTemplateRegistry
    from nexus_graph_builder.hyperedge_extractor import HyperedgeExtractor
    from nexus_llm_gateway import LLMGateway


class GraphBuildService:
    def __init__(
        self,
        metadata_repository,
        graph_repository,
        llm_gateway: "LLMGateway | None" = None,
        template_registry: "DomainTemplateRegistry | None" = None,
        domain: str | None = None,
        hyperedge_extractor: "HyperedgeExtractor | None" = None,
    ) -> None:
        self.metadata_repository = metadata_repository
        self.graph_repository = graph_repository
        self._hyperedge_extractor = hyperedge_extractor
        if llm_gateway is not None:
            self._extractor: LLMEntityExtractor | None = LLMEntityExtractor(
                gateway=llm_gateway,
                template_registry=template_registry,
                domain=domain,
            )
        else:
            self._extractor = None

    def build_from_approved_chunks(self, limit: int = 100) -> GraphBuildResult:
        chunks: list[GraphChunkInput] = self.metadata_repository.list_approved_graph_chunks(limit=limit)
        return GraphBuilder(
            self.graph_repository,
            extractor=self._extractor,
            hyperedge_extractor=self._hyperedge_extractor,
        ).build_from_chunks(chunks)
