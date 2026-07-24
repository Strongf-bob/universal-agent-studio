from __future__ import annotations

import pytest
from temporalio.testing import WorkflowEnvironment
from temporalio.worker import Worker
from universal_agent_studio_api.runs.temporal_adapter import (
    TemporalDurableExecutionAdapter,
)
from universal_agent_studio_runtime.activities.execution import RunExecutionActivities
from universal_agent_studio_runtime.workflows.run import AgentRunWorkflow

from tests.integration.temporal_support import (
    RUN_ID,
    SIGNING_KEY,
    MemoryRuntimePersistence,
    execution_command,
)

TASK_QUEUE = "uas-runtime-v1-integration"


@pytest.mark.asyncio
async def test_temporal_adapter_completes_a_real_workflow() -> None:
    persistence = MemoryRuntimePersistence()
    activities = RunExecutionActivities(
        signing_key=SIGNING_KEY,
        persistence=persistence,
    )
    command = execution_command()

    async with await WorkflowEnvironment.start_time_skipping() as environment:
        adapter = TemporalDurableExecutionAdapter(
            environment.client,
            signing_key=SIGNING_KEY,
            task_queue=TASK_QUEUE,
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
            durable_id = await adapter.start_run(command)
            result = await environment.client.get_workflow_handle(durable_id).result()

    assert durable_id == f"uas-run-{RUN_ID}"
    assert result["status"] == "completed"
    assert result["output"] == {"value": 437}
    assert "signature" not in str(result)
