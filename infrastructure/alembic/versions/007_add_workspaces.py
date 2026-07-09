"""add workspaces and workspace-scoped access

Revision ID: 007_add_workspaces
Revises: 006_add_document_versioning
Create Date: 2026-07-07
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "007_add_workspaces"
down_revision = "006_add_document_versioning"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "workspaces",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("name", sa.String(length=200), nullable=False, unique=True),
        sa.Column("slug", sa.String(length=64), nullable=False, unique=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
    )
    op.create_table(
        "workspace_members",
        sa.Column("workspace_id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", sa.String(length=128), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], ondelete="CASCADE"),
    )

    # Nullable at the DB level: documents ingested via the Phase 1 CLI directory
    # scan have no workspace concept and legitimately keep workspace_id = NULL
    # (admin-only visibility). The upload API (E2/E3) enforces a non-null
    # workspace_id at the application layer for every new upload.
    op.add_column("documents", sa.Column("workspace_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.create_foreign_key(
        "fk_documents_workspace_id", "documents", "workspaces", ["workspace_id"], ["id"], ondelete="SET NULL"
    )
    op.create_index("idx_documents_workspace_id", "documents", ["workspace_id"])

    op.add_column("ingestion_jobs", sa.Column("workspace_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.create_foreign_key(
        "fk_ingestion_jobs_workspace_id", "ingestion_jobs", "workspaces", ["workspace_id"], ["id"], ondelete="CASCADE"
    )
    op.create_index("idx_ingestion_jobs_workspace_id", "ingestion_jobs", ["workspace_id"])


def downgrade() -> None:
    op.drop_index("idx_ingestion_jobs_workspace_id", table_name="ingestion_jobs")
    op.drop_constraint("fk_ingestion_jobs_workspace_id", "ingestion_jobs", type_="foreignkey")
    op.drop_column("ingestion_jobs", "workspace_id")

    op.drop_index("idx_documents_workspace_id", table_name="documents")
    op.drop_constraint("fk_documents_workspace_id", "documents", type_="foreignkey")
    op.drop_column("documents", "workspace_id")

    op.drop_table("workspace_members")
    op.drop_table("workspaces")
