"""slice2_agent_drafts

Revision ID: 0002
Revises: 0001
Create Date: 2026-07-24 22:45:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0002"
down_revision: str | Sequence[str] | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "agent_drafts",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("workspace_id", sa.UUID(), nullable=False),
        sa.Column("project_id", sa.UUID(), nullable=False),
        sa.Column("agent_id", sa.UUID(), nullable=False),
        sa.Column("base_version_id", sa.UUID(), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("digest", sa.String(length=64), nullable=False),
        sa.Column(
            "agent_spec",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
        ),
        sa.Column(
            "layout",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
        ),
        sa.Column("updated_by_owner_id", sa.UUID(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "char_length(digest) = 64",
            name="ck_agent_draft_digest",
        ),
        sa.CheckConstraint(
            "revision > 0",
            name="ck_agent_draft_revision",
        ),
        sa.ForeignKeyConstraint(
            ["agent_id"],
            ["agents.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["base_version_id"],
            ["agent_versions.id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["project_id"],
            ["projects.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["updated_by_owner_id"],
            ["owners.id"],
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["workspace_id"],
            ["workspaces.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("agent_id"),
    )
    op.create_index(
        op.f("ix_agent_drafts_agent_id"),
        "agent_drafts",
        ["agent_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_agent_drafts_base_version_id"),
        "agent_drafts",
        ["base_version_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_agent_drafts_project_id"),
        "agent_drafts",
        ["project_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_agent_drafts_workspace_id"),
        "agent_drafts",
        ["workspace_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_agent_drafts_workspace_id"),
        table_name="agent_drafts",
    )
    op.drop_index(
        op.f("ix_agent_drafts_project_id"),
        table_name="agent_drafts",
    )
    op.drop_index(
        op.f("ix_agent_drafts_base_version_id"),
        table_name="agent_drafts",
    )
    op.drop_index(
        op.f("ix_agent_drafts_agent_id"),
        table_name="agent_drafts",
    )
    op.drop_table("agent_drafts")
