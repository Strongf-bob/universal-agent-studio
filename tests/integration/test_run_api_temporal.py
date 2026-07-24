from __future__ import annotations

import json
from pathlib import Path
from uuid import UUID, uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession
from temporalio.testing import WorkflowEnvironment
from temporalio.worker import Worker
from universal_agent_kernel.contracts.canonical import content_digest
from universal_agent_kernel.contracts.validation import validation_codes
from universal_agent_platform_store.repositories.agents import AgentRepository
from universal_agent_platform_store.scope import RequestScope
from universal_agent_platform_store.session import create_session_factory
from universal_agent_studio_api.agents.service import SqlAgentVersionPersistence
from universal_agent_studio_api.errors import ApiError
from universal_agent_studio_api.runs.service import (
    CreateRunRequest,
    RunService,
    SqlRunPersistence,
)
from universal_agent_studio_api.runs.temporal_adapter import (
    TemporalDurableExecutionAdapter,
)
from universal_agent_studio_runtime.activities.events import SqlRuntimePersistence
from universal_agent_studio_runtime.activities.execution import RunExecutionActivities
from universal_agent_studio_runtime.workflows.run import AgentRunWorkflow

from tests.integration.temporal_support import SIGNING_KEY

ROOT = Path(__file__).parents[2]
GOLDEN_AGENT = (
    ROOT / "contracts" / "examples" / "v0.1.0" / "valid" / "agent.calculator.ru-en.json"
)
TASK_QUEUE = "uas-runtime-v1-api-temporal"


@pytest.mark.asyncio
async def test_run_service_persists_real_temporal_events_and_trace(
    database_engine: AsyncEngine,
    database_session: AsyncSession,
    request_scope: RequestScope,
) -> None:
    spec = json.loads(GOLDEN_AGENT.read_bytes())
    agent_repository = AgentRepository(database_session, request_scope)
    version, _ = await agent_repository.import_version(spec, content_digest(spec))
    await agent_repository.activate(
        agent_key="calculator-agent",
        version_id=version.id,
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
        service = RunService(
            run_persistence=SqlRunPersistence(session_factory),
            agent_persistence=SqlAgentVersionPersistence.from_factory(session_factory),
            durable_execution=durable,
        )
        activities = RunExecutionActivities(
            signing_key=SIGNING_KEY,
            persistence=SqlRuntimePersistence(session_factory),
        )
        async with Worker(
            environment.client,
            task_queue=TASK_QUEUE,
            workflows=[AgentRunWorkflow],
            activities=[activities.execute_run, activities.finalize_cancelled_run],
        ):
            created = await service.create_run(
                CreateRunRequest(
                    schema_version="0.1.0",
                    request_id=UUID("11111111-1111-4111-8111-111111111111"),
                    agent_version_id="calculator-agent-v1",
                    agent_version_digest=content_digest(spec),
                    idempotency_key="integration-run-0001",
                    input={"question": "Сколько будет 19 × 23?"},
                    locale="ru-RU",
                ),
                request_scope,
            )
            await environment.client.get_workflow_handle(
                f"uas-run-{created.run_id}"
            ).result()
            trace = await service.get_trace(created.run_id, request_scope)
            events = await service.list_events(
                created.run_id,
                request_scope,
                after_sequence=0,
            )
            other_project = RequestScope(
                workspace_id=request_scope.workspace_id,
                project_id=uuid4(),
                owner_id=request_scope.owner_id,
            )
            with pytest.raises(ApiError) as cross_project_error:
                await service.get_run(created.run_id, other_project)

    assert trace["status"] == "completed"
    assert trace["output"] == {"value": 437}
    assert len(events) == 8
    assert validation_codes(trace, "run-trace.schema.json") == []
    assert cross_project_error.value.status_code == 404
