# Nexus-KB Phase 1 Rules

## System Objective

Build the Phase 1 MVP core of Nexus-KB, an Enterprise RAG and Knowledge Graph Engine.

Phase 1 is limited to local plain text and Obsidian Markdown ingestion. It must not implement web UI, full RBAC, external enterprise connectors, PDF parsing, DOCX parsing, image parsing, or OCR.

## Strict Guardrails

- Do not use emojis or icons in generated code, comments, console output, documentation, or commit messages.
- Use modular monorepo boundaries:
  - `services/nexus-api`
  - `workers/document-parser`
  - `packages/shared-contracts`
  - `packages/vector-client`
  - `infrastructure`
- Keep backend business logic decoupled from FastAPI and infrastructure clients through ports and adapters.
- Use SHA-256 `content_hash` to skip unmodified files and avoid duplicate chunking or indexing.
- Do not fail silently. Surface parse, database, and Qdrant failures through explicit errors, logs, or ingestion run status.
- Use synthetic data in tests.

## Supported File Scope

Supported in Phase 1:

- `.md`
- `.txt`

Unsupported in Phase 1:

- PDF
- DOC
- DOCX
- Images
- External connector payloads

Unsupported files must be skipped by the loader.

## Data Contract

### documents

- `id`: UUID primary key.
- `source_type`: `local_file` or `obsidian`.
- `source_path`: unique source path.
- `file_extension`: extension such as `.md` or `.txt`.
- `mime_type`: MIME type such as `text/markdown` or `text/plain`.
- `title`: document title.
- `content_hash`: SHA-256 hash.
- `frontmatter`: JSONB.
- `tags`: text array.
- `wikilinks`: text array.
- `created_at`: timestamp.
- `updated_at`: timestamp.

### chunks

- `id`: UUID primary key.
- `document_id`: foreign key to `documents`.
- `chunk_index`: integer.
- `content`: chunk text.
- `content_hash`: SHA-256 hash.
- `token_count`: integer.
- `metadata`: JSONB.
- `qdrant_point_id`: UUID, equal to the chunk UUID.
- `embedding_model`: model name.
- `created_at`: timestamp.

### ingestion_runs

- `id`: UUID primary key.
- `source_path`: scanned path.
- `status`: `running`, `completed`, or `failed`.
- `documents_seen`: integer.
- `documents_indexed`: integer.
- `chunks_indexed`: integer.
- `error_message`: text.
- `started_at`: timestamp.
- `finished_at`: timestamp.

## Qdrant Payload

The Qdrant point ID must match the chunk UUID. Payload must include:

- `document_id`
- `chunk_id`
- `source_type`
- `source_path`
- `file_extension`
- `mime_type`
- `title`
- `tags`
- `wikilinks`
- `frontmatter`
- `chunk_index`

## Execution Order

1. Infrastructure: Docker Compose for PostgreSQL and Qdrant.
2. Shared contracts and vector client.
3. Database models and migrations.
4. Local and Obsidian loader.
5. Chunking and local embeddings.
6. Ingestion pipeline.
7. FastAPI search API.
8. Unit and integration tests.

## Verification

- Unit tests must run without Docker or external APIs.
- Live integration tests must be gated behind an explicit environment variable.
- Docker Compose config should validate before services are started.
