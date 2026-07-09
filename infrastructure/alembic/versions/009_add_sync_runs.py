"""add sync_runs table for Confluence connector sync

Revision ID: 009_add_sync_runs
Revises: 008_add_document_ack
Create Date: 2026-07-07
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "009_add_sync_runs"
down_revision = "008_add_document_ack"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "sync_runs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("space_key", sa.String(length=200), nullable=False),
        sa.Column("workspace_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False, server_default=sa.text("'running'")),
        sa.Column("actor_id", sa.String(length=128), nullable=False),
        sa.Column("pages_seen", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("pages_indexed", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("status IN ('running', 'completed', 'failed')", name="ck_sync_runs_status"),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], ondelete="CASCADE"),
    )
    op.create_index("idx_sync_runs_workspace_id", "sync_runs", ["workspace_id"])

    op.add_column("ingestion_jobs", sa.Column("sync_run_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.create_foreign_key(
        "fk_ingestion_jobs_sync_run_id", "ingestion_jobs", "sync_runs", ["sync_run_id"], ["id"], ondelete="SET NULL"
    )
    op.create_index("idx_ingestion_jobs_sync_run_id", "ingestion_jobs", ["sync_run_id"])


def downgrade() -> None:
    op.drop_index("idx_ingestion_jobs_sync_run_id", table_name="ingestion_jobs")
    op.drop_constraint("fk_ingestion_jobs_sync_run_id", "ingestion_jobs", type_="foreignkey")
    op.drop_column("ingestion_jobs", "sync_run_id")

    op.drop_index("idx_sync_runs_workspace_id", table_name="sync_runs")
    op.drop_table("sync_runs")
