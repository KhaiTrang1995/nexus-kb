"""add document versioning and upload dedup columns

Revision ID: 006_add_document_versioning
Revises: 005_add_ingestion_jobs_table
Create Date: 2026-07-07
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "006_add_document_versioning"
down_revision = "005_add_ingestion_jobs_table"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("documents", sa.Column("current_version", sa.Integer(), nullable=False, server_default=sa.text("1")))

    op.create_table(
        "document_versions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("document_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("version_number", sa.Integer(), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        sa.Column("file_extension", sa.String(length=16), nullable=False),
        sa.Column("mime_type", sa.String(length=128), nullable=False),
        sa.Column("source_path", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
        sa.CheckConstraint("version_number >= 1", name="ck_document_versions_version_number"),
        sa.ForeignKeyConstraint(["document_id"], ["documents.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("document_id", "version_number", name="uq_document_versions_document_version"),
    )
    op.create_index("idx_document_versions_document_id", "document_versions", ["document_id"])

    op.add_column("ingestion_jobs", sa.Column("raw_content_hash", sa.String(length=64), nullable=True))
    op.add_column("ingestion_jobs", sa.Column("target_document_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.create_foreign_key(
        "fk_ingestion_jobs_target_document_id",
        "ingestion_jobs",
        "documents",
        ["target_document_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index("idx_ingestion_jobs_raw_content_hash", "ingestion_jobs", ["raw_content_hash"])


def downgrade() -> None:
    op.drop_index("idx_ingestion_jobs_raw_content_hash", table_name="ingestion_jobs")
    op.drop_constraint("fk_ingestion_jobs_target_document_id", "ingestion_jobs", type_="foreignkey")
    op.drop_column("ingestion_jobs", "target_document_id")
    op.drop_column("ingestion_jobs", "raw_content_hash")
    op.drop_index("idx_document_versions_document_id", table_name="document_versions")
    op.drop_table("document_versions")
    op.drop_column("documents", "current_version")
