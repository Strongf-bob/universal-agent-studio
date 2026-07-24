from __future__ import annotations

import asyncio
from collections.abc import Mapping
from uuid import UUID

import pytest
from temporalio.testing import WorkflowEnvironment
from temporalio.worker import Worker
from universal_agent_kernel.contracts.validation import validation_codes
from universal_agent_platform_store.scope import RequestScope
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

TASK_QUEUE = "uas-runtime-v1-cancellation"


class BlockingToolPersistence(MemoryRuntimePersistence):
    def __init__(self) -> None:
        super().__init__()
        self.tool_started = asyncio.Event()
        self.never_release = asyncio.Event()

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
        del scope, run_id, node_id, invocation_key, tool_id, arguments
        self.tool_started.set()
        await self.never_release.wait()
        raise AssertionError("unreachable")


@pytest.mark.asyncio
async def test_product_signal_creates_terminal_cancelled_trace() -> None:
    persistence = BlockingToolPersistence()
    activities = RunExecutionActivities(
        signing_key=SIGNING_KEY,
        persistence=persistence,
    )

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
            durable_id = await adapter.start_run(execution_command())
            await asyncio.wait_for(persistence.tool_started.wait(), timeout=5)
            assert await adapter.request_cancel(RUN_ID) == "requested"
            trace = await environment.client.get_workflow_handle(durable_id).result()

    assert trace["status"] == "cancelled"
    assert trace["events"][-1]["type"] == "run.cancelled"
    assert sum(event["type"] == "run.cancelled" for event in trace["events"]) == 1
    assert validation_codes(trace, "run-trace.schema.json") == []
    assert "signature" not in str(trace)
