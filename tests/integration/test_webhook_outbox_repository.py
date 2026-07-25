from __future__ import annotations

from sqlalchemy import UniqueConstraint
from universal_agent_platform_store.models import Base


def test_webhook_delivery_constraints_are_registered() -> None:
    delivery = Base.metadata.tables["webhook_deliveries"]
    constraint_columns = {
        tuple(column.name for column in constraint.columns)
        for constraint in delivery.constraints
        if isinstance(constraint, UniqueConstraint)
    }

    assert ("subscription_id", "run_id", "event_sequence") in constraint_columns
