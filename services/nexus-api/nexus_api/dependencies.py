from __future__ import annotations

import logging
from functools import lru_cache
from pathlib import Path

from nexus_api.config import get_settings
from nexus_document_parser.embedding import SentenceTransformerEmbeddingProvider
from nexus_document_parser.sqlalchemy_repository import SQLAlchemyMetadataRepository
from nexus_graph_builder import SQLAlchemyGraphRepository
from nexus_vector.client import NexusVectorClient

logger = logging.getLogger(__name__)


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
        logger.warning("Unknown LLM_PROVIDER=%s -- LLM extraction disabled", settings.llm_provider)
        return None
    route = ModelRoute(task_type="entity_extraction", provider=settings.llm_provider, model=settings.llm_model)
    default = ModelRoute(task_type="default", provider=settings.llm_provider, model=settings.llm_model)
    return LLMGateway(providers={settings.llm_provider: provider}, routes=[route], default_route=default)


@lru_cache(maxsize=1)
def build_template_registry():
    templates_dir = Path(__file__).parents[3] / "data" / "domain-templates"
    if not templates_dir.exists():
        return None
    from nexus_graph_builder.domain_template import DomainTemplateRegistry
    return DomainTemplateRegistry(templates_dir)


@lru_cache(maxsize=1)
def build_hyperedge_extractor():
    gateway = build_llm_gateway()
    if gateway is None:
        return None
    from nexus_graph_builder.hyperedge_extractor import HyperedgeExtractor
    return HyperedgeExtractor(gateway=gateway)


@lru_cache(maxsize=1)
def build_confluence_client():
    settings = get_settings()
    if not settings.confluence_base_url or not settings.confluence_api_token:
        return None
    from nexus_confluence_bridge.http_client import HttpConfluenceClient

    return HttpConfluenceClient(base_url=settings.confluence_base_url, api_token=settings.confluence_api_token)


@lru_cache(maxsize=1)
def build_graph_vector_client() -> NexusVectorClient:
    settings = get_settings()
    return NexusVectorClient(
        host=settings.qdrant_host,
        port=settings.qdrant_port,
        collection_name="nexus_graph",
        vector_size=settings.embedding_dimension,
    )
