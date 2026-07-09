from __future__ import annotations

import argparse
import os

from nexus_document_parser.embedding import SentenceTransformerEmbeddingProvider
from nexus_document_parser.job_worker import JobWorker
from nexus_document_parser.pipeline import IngestionPipeline
from nexus_document_parser.sqlalchemy_repository import SQLAlchemyMetadataRepository
from nexus_vector.client import NexusVectorClient


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the ingestion_jobs FIFO worker loop")
    parser.add_argument(
        "--poll-interval",
        type=float,
        default=float(os.getenv("INGESTION_WORKER_POLL_SECONDS", "2.0")),
        help="Seconds to sleep when the queue is empty",
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

    repository = SQLAlchemyMetadataRepository(postgres_dsn)
    pipeline = IngestionPipeline(
        repository=repository,
        vector_client=NexusVectorClient(
            host=qdrant_host,
            port=qdrant_port,
            collection_name=qdrant_collection,
            vector_size=embedding_dimension,
        ),
        embedding_provider=SentenceTransformerEmbeddingProvider(embedding_model),
    )
    JobWorker(repository, pipeline).run_forever(poll_interval_seconds=args.poll_interval)


if __name__ == "__main__":
    main()
