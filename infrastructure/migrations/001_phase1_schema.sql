CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE TABLE IF NOT EXISTS documents (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    source_type VARCHAR(32) NOT NULL CHECK (source_type IN ('local_file', 'obsidian')),
    source_path TEXT NOT NULL UNIQUE,
    file_extension VARCHAR(16) NOT NULL,
    mime_type VARCHAR(128) NOT NULL,
    title TEXT NOT NULL,
    content_hash CHAR(64) NOT NULL,
    frontmatter JSONB NOT NULL DEFAULT '{}'::jsonb,
    tags TEXT[] NOT NULL DEFAULT ARRAY[]::TEXT[],
    wikilinks TEXT[] NOT NULL DEFAULT ARRAY[]::TEXT[],
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS chunks (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    document_id UUID NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    chunk_index INTEGER NOT NULL,
    content TEXT NOT NULL,
    content_hash CHAR(64) NOT NULL,
    token_count INTEGER NOT NULL,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    qdrant_point_id UUID NOT NULL,
    embedding_model TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (document_id, chunk_index),
    UNIQUE (qdrant_point_id)
);

CREATE TABLE IF NOT EXISTS ingestion_runs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    source_path TEXT NOT NULL,
    status VARCHAR(32) NOT NULL CHECK (status IN ('running', 'completed', 'failed')),
    documents_seen INTEGER NOT NULL DEFAULT 0,
    documents_indexed INTEGER NOT NULL DEFAULT 0,
    chunks_indexed INTEGER NOT NULL DEFAULT 0,
    error_message TEXT,
    started_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    finished_at TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_documents_source_type ON documents(source_type);
CREATE INDEX IF NOT EXISTS idx_documents_file_extension ON documents(file_extension);
CREATE INDEX IF NOT EXISTS idx_documents_mime_type ON documents(mime_type);
CREATE INDEX IF NOT EXISTS idx_documents_content_hash ON documents(content_hash);
CREATE INDEX IF NOT EXISTS idx_documents_frontmatter_gin ON documents USING GIN (frontmatter);
CREATE INDEX IF NOT EXISTS idx_documents_tags_gin ON documents USING GIN (tags);
CREATE INDEX IF NOT EXISTS idx_documents_wikilinks_gin ON documents USING GIN (wikilinks);
CREATE INDEX IF NOT EXISTS idx_chunks_document_id ON chunks(document_id);
CREATE INDEX IF NOT EXISTS idx_chunks_content_hash ON chunks(content_hash);
CREATE INDEX IF NOT EXISTS idx_chunks_metadata_gin ON chunks USING GIN (metadata);
CREATE INDEX IF NOT EXISTS idx_ingestion_runs_status ON ingestion_runs(status);
