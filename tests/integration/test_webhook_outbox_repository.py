from __future__ import annotations

import json
from pathlib import Path
from typing import Any, cast
from uuid import uuid4

import pytest
from sqlalchemy import UniqueConstraint, select
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker
from universal_agent_kernel.contracts.canonical import content_digest
from universal_agent_platform_store.models import (
    Base,
    Run,
    WebhookDelivery,
)
from universal_agent_platform_store.repositories.agents import AgentRepository
from universal_agent_platform_store.repositories.webhooks import WebhookRepository
from universal_agent_platform_store.scope import RequestScope
from universal_agent_studio_runtime.activities.events import SqlRuntimePersistence

ROOT = Path(__file__).parents[2]
GOLDEN = (
    ROOT
    / "contracts"
    / "examples"
    / "v0.1.0"
    / "valid"
    / "agent.calculator.ru-en.json"
)


def test_webhook_delivery_constraints_are_registered() -> None:
    delivery = Base.metadata.tables["webhook_deliveries"]
    constraint_columns = {
        tuple(column.name for column in constraint.columns)
        for constraint in delivery.constraints
        if isinstance(constraint, UniqueConstraint)
    }

    assert ("subscription_id", "run_id", "event_sequence") in constraint_columns


@pytest.mark.asyncio
async def test_terminal_trace_atomically_enqueues_sanitized_delivery(
    database_engine: AsyncEngine,
    database_session: AsyncSession,
    request_scope: RequestScope,
) -> None:
    spec = cast(dict[str, Any], json.loads(GOLDEN.read_text(encoding="utf-8")))
    version, _ = await AgentRepository(
        database_session,
        request_scope,
    ).import_version(spec, content_digest(spec))
    subscription = await WebhookRepository(
        database_session,
        request_scope,
    ).create(
        "calculator-agent",
        label="Acceptance",
        target_url="http://example.test:9090/hooks/terminal",
        events=["run.completed"],
        signing_key_id=uuid4(),
    )
    run = Run(
        id=uuid4(),
        workspace_id=request_scope.workspace_id,
        project_id=request_scope.project_id,
        agent_version_id=version.id,
        status="running",
        locale="en-US",
        input_document={"question": "19 * 23"},
        cancel_requested=False,
    )
    database_session.add(run)
    await database_session.commit()
    trace = {
        "schema_version": "0.1.0",
        "status": "completed",
        "output": {"value": 437},
        "events": [
            {
                "sequence": 8,
                "type": "run.completed",
                "occurred_at": "2026-07-25T12:00:00Z",
                "payload": {"output": {"value": 437}},
            }
        ],
        "prompt": "must-not-enter-public-delivery",
    }

    persistence = SqlRuntimePersistence(
        async_sessionmaker(database_engine, expire_on_commit=False)
    )
    await persistence.finalize_trace(
        scope=request_scope,
        run_id=run.id,
        document=trace,
    )
    await persistence.finalize_trace(
        scope=request_scope,
        run_id=run.id,
        document=trace,
    )

    async with AsyncSession(database_engine) as verification:
        deliveries = list(
            await verification.scalars(select(WebhookDelivery))
        )
    assert len(deliveries) == 1
    delivery = deliveries[0]
    assert delivery.subscription_id == subscription.id
    assert delivery.event_sequence == 8
    assert delivery.payload["result"] == {"value": 437}
    assert "prompt" not in json.dumps(delivery.payload)
