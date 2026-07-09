from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache


@dataclass(frozen=True)
class Settings:
    postgres_dsn: str = os.getenv("POSTGRES_DSN", "postgresql+psycopg://nexus:change-me@localhost:5432/nexus_kb")
    qdrant_host: str = os.getenv("QDRANT_HOST", "localhost")
    qdrant_port: int = int(os.getenv("QDRANT_HTTP_PORT", "6333"))
    qdrant_collection: str = os.getenv("QDRANT_COLLECTION", "nexus_chunks")
    embedding_model: str = os.getenv("EMBEDDING_MODEL", os.getenv("NEXUS_EMBEDDING_MODEL", "BAAI/bge-m3"))
    embedding_dimension: int = int(os.getenv("NEXUS_EMBEDDING_DIMENSION", "1024"))
    llm_enabled: bool = os.getenv("LLM_ENABLED", "false").lower() in ("1", "true", "yes")
    llm_provider: str = os.getenv("LLM_PROVIDER", "ollama")
    llm_model: str = os.getenv("LLM_MODEL", "llama3.2:3b")
    llm_base_url: str = os.getenv("LLM_BASE_URL", "http://localhost:11434")
    llm_api_key: str = os.getenv("LLM_API_KEY", "")
    graph_domain: str = os.getenv("GRAPH_DOMAIN", "general")
    audit_log_dir: str = os.getenv("AUDIT_LOG_DIR", "./data")
    upload_staging_dir: str = os.getenv("UPLOAD_STAGING_DIR", "./data/uploads")
    upload_max_files_per_batch: int = int(os.getenv("UPLOAD_MAX_FILES_PER_BATCH", "5"))
    upload_max_file_size_mb: int = int(os.getenv("UPLOAD_MAX_FILE_SIZE_MB", "50"))
    ingestion_job_max_attempts: int = int(os.getenv("INGESTION_JOB_MAX_ATTEMPTS", "3"))
    confluence_base_url: str = os.getenv("CONFLUENCE_BASE_URL", "")
    confluence_api_token: str = os.getenv("CONFLUENCE_API_TOKEN", "")
    confluence_sync_page_limit: int = int(os.getenv("CONFLUENCE_SYNC_PAGE_LIMIT", "100"))


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
