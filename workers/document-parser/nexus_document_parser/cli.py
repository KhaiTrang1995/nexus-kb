from __future__ import annotations

import argparse
import os

from nexus_shared.contracts import SourceType
from nexus_document_parser.embedding import SentenceTransformerEmbeddingProvider
from nexus_document_parser.pipeline import IngestionPipeline
from nexus_document_parser.sqlalchemy_repository import SQLAlchemyMetadataRepository
from nexus_vector.client import NexusVectorClient


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Ingest local Nexus-KB documents")
    parser.add_argument("source_path", help="File, folder, or Obsidian vault path")
    parser.add_argument(
        "--source-type",
        choices=[item.value for item in SourceType],
        default=SourceType.LOCAL_FILE.value,
        help="Source type to store in metadata",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    postgres_dsn = os.getenv("POSTGRES_DSN", "postgresql+psycopg://nexus:change-me@localhost:5432/nexus_kb")
    qdrant_host = os.getenv("QDRANT_HOST", "localhost")
    qdrant_port = int(os.getenv("QDRANT_HTTP_PORT", "6333"))
    qdrant_collection = os.getenv("QDRANT_COLLECTION", "nexus_chunks")
    embedding_model = os.getenv("NEXUS_EMBEDDING_MODEL", "BAAI/bge-m3")
    embedding_dimension = int(os.getenv("NEXUS_EMBEDDING_DIMENSION", "1024"))

    pipeline = IngestionPipeline(
        repository=SQLAlchemyMetadataRepository(postgres_dsn),
        vector_client=NexusVectorClient(
            host=qdrant_host,
            port=qdrant_port,
            collection_name=qdrant_collection,
            vector_size=embedding_dimension,
        ),
        embedding_provider=SentenceTransformerEmbeddingProvider(embedding_model),
    )
    result = pipeline.ingest(args.source_path, SourceType(args.source_type))
    print(result.model_dump_json(indent=2))


if __name__ == "__main__":
    main()
