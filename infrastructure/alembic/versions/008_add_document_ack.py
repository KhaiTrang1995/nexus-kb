"""add document uploader/ack tracking for the two-tier review gate

Revision ID: 008_add_document_ack
Revises: 007_add_workspaces
Create Date: 2026-07-07
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "008_add_document_ack"
down_revision = "007_add_workspaces"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("documents", sa.Column("uploaded_by", sa.String(length=128), nullable=True))
    op.add_column("documents", sa.Column("acked_by", sa.String(length=128), nullable=True))
    op.add_column("documents", sa.Column("acked_at", sa.DateTime(timezone=True), nullable=True))
    op.create_index("idx_documents_acked_at", "documents", ["acked_at"])

    op.add_column("document_versions", sa.Column("uploaded_by", sa.String(length=128), nullable=True))
    op.add_column("document_versions", sa.Column("acked_by", sa.String(length=128), nullable=True))
    op.add_column("document_versions", sa.Column("acked_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column("document_versions", "acked_at")
    op.drop_column("document_versions", "acked_by")
    op.drop_column("document_versions", "uploaded_by")

    op.drop_index("idx_documents_acked_at", table_name="documents")
    op.drop_column("documents", "acked_at")
    op.drop_column("documents", "acked_by")
    op.drop_column("documents", "uploaded_by")
