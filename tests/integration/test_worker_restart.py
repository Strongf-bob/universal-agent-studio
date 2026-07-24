from __future__ import annotations

import asyncio
from collections.abc import Mapping
from uuid import UUID

import pytest
from temporalio.testing import WorkflowEnvironment
from temporalio.worker import Worker
from universal_agent_platform_store.scope import RequestScope
from universal_agent_studio_api.runs.temporal_adapter import (
    TemporalDurableExecutionAdapter,
)
from universal_agent_studio_runtime.activities.execution import RunExecutionActivities
from universal_agent_studio_runtime.workflows.run import AgentRunWorkflow

from tests.integration.temporal_support import (
    SIGNING_KEY,
    MemoryRuntimePersistence,
    execution_command,
)

TASK_QUEUE = "uas-runtime-v1-restart"


class FailOnceAfterToolPersistence(MemoryRuntimePersistence):
    def __init__(self) -> None:
        super().__init__()
        self.first_tool_result_persisted = asyncio.Event()
        self.should_fail = True

    async def invoke_calculator_once(
        self,
        *,
        scope: RequestScope,
        run_id: UUID,
        node_id: str,
        invocation_key: str,
        tool_id: str,
        arguments: Mapping[str, object],
    ) -> Mapping[str, object]:
        result = await super().invoke_calculator_once(
            scope=scope,
            run_id=run_id,
            node_id=node_id,
            invocation_key=invocation_key,
            tool_id=tool_id,
            arguments=arguments,
        )
        if self.should_fail:
            self.should_fail = False
            self.first_tool_result_persisted.set()
            raise RuntimeError("controlled_worker_loss_after_tool")
        return result


@pytest.mark.asyncio
async def test_worker_restart_does_not_repeat_logical_tool_invocation() -> None:
    persistence = FailOnceAfterToolPersistence()
    activities = RunExecutionActivities(
        signing_key=SIGNING_KEY,
        persistence=persistence,
    )

    async with await WorkflowEnvironment.start_local() as environment:
        adapter = TemporalDurableExecutionAdapter(
            environment.client,
            signing_key=SIGNING_KEY,
            task_queue=TASK_QUEUE,
        )
        first_worker = Worker(
            environment.client,
            task_queue=TASK_QUEUE,
            workflows=[AgentRunWorkflow],
            activities=[
                activities.execute_run,
                activities.finalize_cancelled_run,
                activities.finalize_failed_run,
            ],
        )
        first_worker_task = asyncio.create_task(first_worker.run())
        durable_id = await adapter.start_run(execution_command())
        await asyncio.wait_for(
            persistence.first_tool_result_persisted.wait(),
            timeout=5,
        )
        await first_worker.shutdown()
        await first_worker_task

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
            trace = await environment.client.get_workflow_handle(durable_id).result()

    assert trace["status"] == "completed"
    assert trace["output"] == {"value": 437}
    assert persistence.logical_tool_invocations == 1
    assert [event["sequence"] for event in trace["events"]] == list(range(1, 9))
