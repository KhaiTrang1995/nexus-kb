from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    postgres_dsn: str = os.getenv("POSTGRES_DSN", "postgresql+psycopg://nexus:change-me@localhost:5432/nexus_kb")
    qdrant_host: str = os.getenv("QDRANT_HOST", "localhost")
    qdrant_port: int = int(os.getenv("QDRANT_HTTP_PORT", "6333"))
    qdrant_collection: str = os.getenv("QDRANT_COLLECTION", "nexus_chunks")
    embedding_model: str = os.getenv("EMBEDDING_MODEL", os.getenv("NEXUS_EMBEDDING_MODEL", "BAAI/bge-m3"))
    embedding_dimension: int = int(os.getenv("NEXUS_EMBEDDING_DIMENSION", "1024"))
    # LLM extraction (Phase 6+)
    llm_enabled: bool = os.getenv("LLM_ENABLED", "false").lower() in ("1", "true", "yes")
    llm_provider: str = os.getenv("LLM_PROVIDER", "ollama")
    llm_model: str = os.getenv("LLM_MODEL", "llama3.2:3b")
    llm_base_url: str = os.getenv("LLM_BASE_URL", "http://localhost:11434")
    llm_api_key: str = os.getenv("LLM_API_KEY", "")
    graph_domain: str = os.getenv("GRAPH_DOMAIN", "general")


def get_settings() -> Settings:
    return Settings()
