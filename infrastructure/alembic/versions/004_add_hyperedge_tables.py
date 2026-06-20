"""add hyperedge tables

Revision ID: 004_add_hyperedge_tables
Revises: 003_add_graph_tables
Create Date: 2026-06-20
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "004_add_hyperedge_tables"
down_revision = "003_add_graph_tables"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "graph_hyperedges",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("relationship_type", sa.String(length=128), nullable=False, server_default="INVOLVES"),
        sa.Column("label", sa.Text(), nullable=False, server_default=""),
        sa.Column("confidence", sa.Float(), nullable=False, server_default="1.0"),
        sa.Column(
            "provenance",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
    )
    op.create_table(
        "graph_hyperedge_members",
        sa.Column(
            "hyperedge_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("graph_hyperedges.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column(
            "entity_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("graph_entities.id", ondelete="CASCADE"),
            primary_key=True,
        ),
    )
    op.create_index(
        "idx_graph_hyperedge_members_entity",
        "graph_hyperedge_members",
        ["entity_id"],
    )


def downgrade() -> None:
    op.drop_table("graph_hyperedge_members")
    op.drop_table("graph_hyperedges")
