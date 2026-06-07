from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    postgres_dsn: str = os.getenv("POSTGRES_DSN", "postgresql+psycopg://nexus:change-me@localhost:5432/nexus_kb")
    qdrant_host: str = os.getenv("QDRANT_HOST", "localhost")
    qdrant_port: int = int(os.getenv("QDRANT_HTTP_PORT", "6333"))
    qdrant_collection: str = os.getenv("QDRANT_COLLECTION", "nexus_chunks")
    embedding_model: str = os.getenv("NEXUS_EMBEDDING_MODEL", "BAAI/bge-m3")
    embedding_dimension: int = int(os.getenv("NEXUS_EMBEDDING_DIMENSION", "1024"))


def get_settings() -> Settings:
    return Settings()
