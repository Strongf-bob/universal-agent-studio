from __future__ import annotations

import copy
import json
from pathlib import Path
from uuid import UUID

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession
from temporalio.testing import WorkflowEnvironment
from temporalio.worker import Worker
from universal_agent_kernel.contracts.canonical import content_digest
from universal_agent_platform_store.models import Agent, AgentVersion
from universal_agent_platform_store.repositories.agents import AgentRepository
from universal_agent_platform_store.scope import RequestScope
from universal_agent_platform_store.session import create_session_factory
from universal_agent_studio_api.agents.draft_service import (
    DraftService,
    SqlAgentDraftPersistence,
)
from universal_agent_studio_api.agents.drafts import (
    DraftTestRunRequest,
    UpdateAgentDraftRequest,
)
from universal_agent_studio_api.agents.service import SqlAgentVersionPersistence
from universal_agent_studio_api.runs.service import RunService, SqlRunPersistence
from universal_agent_studio_api.runs.temporal_adapter import (
    TemporalDurableExecutionAdapter,
)
from universal_agent_studio_runtime.activities.events import SqlRuntimePersistence
from universal_agent_studio_runtime.activities.execution import RunExecutionActivities
from universal_agent_studio_runtime.workflows.run import AgentRunWorkflow

from tests.integration.temporal_support import SIGNING_KEY

ROOT = Path(__file__).parents[2]
GOLDEN_AGENT = (
    ROOT
    / "contracts"
    / "examples"
    / "v0.1.0"
    / "valid"
    / "agent.calculator.ru-en.json"
)
TASK_QUEUE = "uas-runtime-v1-draft-temporal"


@pytest.mark.asyncio
async def test_draft_snapshot_runs_without_changing_active_version(
    database_engine: AsyncEngine,
    database_session: AsyncSession,
    request_scope: RequestScope,
) -> None:
    spec = json.loads(GOLDEN_AGENT.read_bytes())
    repository = AgentRepository(database_session, request_scope)
    active, _ = await repository.import_version(spec, content_digest(spec))
    await repository.activate(
        agent_key="calculator-agent",
        version_id=active.id,
        expected_previous_version_id=None,
    )
    await database_session.commit()
    session_factory = create_session_factory(database_engine)

    async with await WorkflowEnvironment.start_time_skipping() as environment:
        durable = TemporalDurableExecutionAdapter(
            environment.client,
            signing_key=SIGNING_KEY,
            task_queue=TASK_QUEUE,
        )
        version_persistence = SqlAgentVersionPersistence.from_factory(
            session_factory
        )
        run_service = RunService(
            run_persistence=SqlRunPersistence(session_factory),
            agent_persistence=version_persistence,
            durable_execution=durable,
        )
        draft_service = DraftService(
            SqlAgentDraftPersistence.from_factory(session_factory),
            agent_persistence=version_persistence,
            run_service=run_service,
        )
        draft, _ = await draft_service.create(
            "calculator-agent",
            request_scope,
        )
        changed = copy.deepcopy(draft.agent_spec)
        changed["localized_metadata"]["name"]["en-US"] = "Draft Math Agent"
        saved = await draft_service.update(
            "calculator-agent",
            UpdateAgentDraftRequest(
                expected_revision=1,
                agent_spec=changed,
                layout=draft.layout,
            ),
            request_scope,
        )
        activities = RunExecutionActivities(
            signing_key=SIGNING_KEY,
            persistence=SqlRuntimePersistence(session_factory),
        )
        async with Worker(
            environment.client,
            task_queue=TASK_QUEUE,
            workflows=[AgentRunWorkflow],
            activities=[
                activities.execute_run,
                activities.finalize_cancelled_run,
                activities.finalize_failed_run,
            ],
        ):
            created = await draft_service.create_test_run(
                "calculator-agent",
                DraftTestRunRequest(
                    expected_revision=2,
                    request_id=UUID(
                        "44444444-4444-4444-8444-444444444444"
                    ),
                    idempotency_key="draft-temporal-0001",
                    input={"question": "What is 19 × 23?"},
                    locale="en-US",
                ),
                request_scope,
            )
            await environment.client.get_workflow_handle(
                f"uas-run-{created.run_id}"
            ).result()
            trace = await run_service.get_trace(
                created.run_id,
                request_scope,
            )

    persisted_active = await version_persistence.get_active_for_agent(
        scope=request_scope,
        agent_id="calculator-agent",
    )
    async with AsyncSession(database_engine) as session:
        snapshot = await session.scalar(
            select(AgentVersion)
            .join(Agent, Agent.id == AgentVersion.agent_id)
            .where(
                Agent.agent_key == "calculator-agent",
                AgentVersion.digest == saved.digest,
            )
        )

    assert persisted_active is not None
    assert persisted_active.public_id == "calculator-agent-v1"
    assert snapshot is not None
    assert snapshot.provenance == {
        "kind": "draft-test-snapshot",
        "draft_id": "calculator-agent-draft",
        "draft_revision": 2,
        "draft_digest": saved.digest,
    }
    assert trace["agent_version_id"] == "calculator-agent-v2"
    assert trace["agent_version_digest"] == saved.digest
    assert trace["output"] == {"value": 437}
