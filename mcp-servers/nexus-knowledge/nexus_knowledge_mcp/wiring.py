from __future__ import annotations

from nexus_knowledge_mcp.auth import InternalJwtVerifier
from nexus_knowledge_mcp.bridge import NexusKnowledgeBridge


def build_bridge() -> NexusKnowledgeBridge:
    """Constructs a bridge wired to the real search/RAG stack.

    Kept out of bridge.py so that module stays free of any dependency on how
    SearchService/RagService/the repository get built (those live in
    services/nexus-api and require its own PYTHONPATH entries, plus a live
    Postgres/Qdrant -- exactly like running nexus-api itself).
    """
    from nexus_api.dependencies import (
        build_embedding_provider,
        build_graph_repository,
        build_llm_gateway,
        build_repository,
        build_vector_client,
    )
    from nexus_api.rag import RagService
    from nexus_api.search import SearchService

    repository = build_repository()
    search_service = SearchService(
        repository=repository,
        vector_client=build_vector_client(),
        embedding_provider=build_embedding_provider(),
        graph_repository=build_graph_repository(),
    )
    rag_service = RagService(search_service=search_service, llm_gateway=build_llm_gateway())

    return NexusKnowledgeBridge(
        token_verifier=InternalJwtVerifier(),
        search_service=search_service,
        rag_service=rag_service,
        repository=repository,
    )
