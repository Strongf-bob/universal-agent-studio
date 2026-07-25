"""slice3_publication_hardening

Revision ID: 0004
Revises: 0003
Create Date: 2026-07-25 20:30:00
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0004"
down_revision: str | Sequence[str] | None = "0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_check_constraint(
        "ck_agent_publication_rollback_changes_version",
        "agent_publication_events",
        (
            "event_type != 'rollback' "
            "OR previous_version_id IS DISTINCT FROM selected_version_id"
        ),
    )
    op.execute(
        """
        CREATE FUNCTION reject_agent_publication_event_mutation()
        RETURNS trigger
        LANGUAGE plpgsql
        AS $$
        BEGIN
            RAISE EXCEPTION
                'agent_publication_events are append-only';
        END;
        $$
        """
    )
    op.execute(
        """
        CREATE TRIGGER tr_agent_publication_events_append_only
        BEFORE UPDATE OR DELETE ON agent_publication_events
        FOR EACH ROW
        EXECUTE FUNCTION reject_agent_publication_event_mutation()
        """
    )


def downgrade() -> None:
    op.execute(
        """
        DROP TRIGGER IF EXISTS tr_agent_publication_events_append_only
        ON agent_publication_events
        """
    )
    op.execute(
        "DROP FUNCTION IF EXISTS reject_agent_publication_event_mutation()"
    )
    op.drop_constraint(
        "ck_agent_publication_rollback_changes_version",
        "agent_publication_events",
        type_="check",
    )
