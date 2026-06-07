"""add graph tables

Revision ID: 003_add_graph_tables
Revises: 002_add_audit_and_review_tables
Create Date: 2026-06-07
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "003_add_graph_tables"
down_revision = "002_add_audit_and_review_tables"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "graph_entities",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("normalized_name", sa.Text(), nullable=False),
        sa.Column("entity_type", sa.String(length=64), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("provenance", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
        sa.UniqueConstraint("normalized_name", "entity_type", name="uq_graph_entities_identity"),
    )
    op.create_table(
        "graph_relationships",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("source_entity_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("target_entity_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("relationship_type", sa.String(length=64), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("provenance", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
        sa.ForeignKeyConstraint(["source_entity_id"], ["graph_entities.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["target_entity_id"], ["graph_entities.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("source_entity_id", "target_entity_id", "relationship_type", name="uq_graph_relationships_identity"),
    )
    op.create_index("idx_graph_entities_normalized_name", "graph_entities", ["normalized_name"])
    op.create_index("idx_graph_relationships_source", "graph_relationships", ["source_entity_id"])
    op.create_index("idx_graph_relationships_target", "graph_relationships", ["target_entity_id"])


def downgrade() -> None:
    op.drop_table("graph_relationships")
    op.drop_table("graph_entities")
