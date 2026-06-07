"""create phase1 schema

Revision ID: 001_phase1_schema
Revises:
Create Date: 2026-06-07
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "001_phase1_schema"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto")
    op.create_table(
        "documents",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("source_type", sa.String(length=32), nullable=False),
        sa.Column("source_path", sa.Text(), nullable=False),
        sa.Column("file_extension", sa.String(length=16), nullable=False),
        sa.Column("mime_type", sa.String(length=128), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        sa.Column("frontmatter", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("tags", postgresql.ARRAY(sa.Text()), nullable=False, server_default=sa.text("ARRAY[]::TEXT[]")),
        sa.Column("wikilinks", postgresql.ARRAY(sa.Text()), nullable=False, server_default=sa.text("ARRAY[]::TEXT[]")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
        sa.CheckConstraint("source_type IN ('local_file', 'obsidian')", name="ck_documents_source_type"),
        sa.UniqueConstraint("source_path"),
    )
    op.create_table(
        "chunks",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("document_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("chunk_index", sa.Integer(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        sa.Column("token_count", sa.Integer(), nullable=False),
        sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("qdrant_point_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("embedding_model", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
        sa.ForeignKeyConstraint(["document_id"], ["documents.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("document_id", "chunk_index"),
        sa.UniqueConstraint("qdrant_point_id"),
    )
    op.create_table(
        "ingestion_runs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("source_path", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("documents_seen", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("documents_indexed", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("chunks_indexed", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("error_message", sa.Text()),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
        sa.Column("finished_at", sa.DateTime(timezone=True)),
        sa.CheckConstraint("status IN ('running', 'completed', 'failed')", name="ck_ingestion_runs_status"),
    )
    op.create_index("idx_documents_source_type", "documents", ["source_type"])
    op.create_index("idx_documents_file_extension", "documents", ["file_extension"])
    op.create_index("idx_documents_mime_type", "documents", ["mime_type"])
    op.create_index("idx_documents_content_hash", "documents", ["content_hash"])
    op.create_index("idx_documents_frontmatter_gin", "documents", ["frontmatter"], postgresql_using="gin")
    op.create_index("idx_documents_tags_gin", "documents", ["tags"], postgresql_using="gin")
    op.create_index("idx_documents_wikilinks_gin", "documents", ["wikilinks"], postgresql_using="gin")
    op.create_index("idx_chunks_document_id", "chunks", ["document_id"])
    op.create_index("idx_chunks_content_hash", "chunks", ["content_hash"])
    op.create_index("idx_chunks_metadata_gin", "chunks", ["metadata"], postgresql_using="gin")
    op.create_index("idx_ingestion_runs_status", "ingestion_runs", ["status"])


def downgrade() -> None:
    op.drop_table("ingestion_runs")
    op.drop_table("chunks")
    op.drop_table("documents")
