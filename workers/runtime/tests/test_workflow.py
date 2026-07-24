from __future__ import annotations

from copy import deepcopy
from uuid import uuid5

import pytest
from support import (
    RUN_ID,
    SIGNING_KEY,
    MemoryRuntimePersistence,
    execution_command,
)
from temporalio.testing import WorkflowEnvironment
from temporalio.worker import Worker
from universal_agent_kernel.contracts.validation import validation_codes
from universal_agent_kernel.execution.envelope import sign_execution_command
from universal_agent_studio_runtime.activities.execution import RunExecutionActivities
from universal_agent_studio_runtime.workflows.run import AgentRunWorkflow

TASK_QUEUE = "uas-runtime-v1-workflow-test"


@pytest.mark.asyncio
async def test_workflow_executes_golden_run_with_stable_events() -> None:
    persistence = MemoryRuntimePersistence()
    activities = RunExecutionActivities(
        signing_key=SIGNING_KEY,
        persistence=persistence,
    )
    envelope = sign_execution_command(execution_command(), SIGNING_KEY)

    async with await WorkflowEnvironment.start_time_skipping() as environment:
        async with Worker(
            environment.client,
            task_queue=TASK_QUEUE,
            workflows=[AgentRunWorkflow],
            activities=[activities.execute_run, activities.finalize_cancelled_run],
        ):
            result = await environment.client.execute_workflow(
                AgentRunWorkflow.run,
                envelope,
                id=f"uas-run-{RUN_ID}",
                task_queue=TASK_QUEUE,
            )

    assert result["status"] == "completed"
    assert result["output"] == {"value": 437}
    assert [event["type"] for event in result["events"]] == [
        "run.started",
        "node.started",
        "model.requested",
        "model.completed",
        "tool.requested",
        "tool.completed",
        "node.completed",
        "run.completed",
    ]
    assert [event["event_id"] for event in result["events"]] == [
        str(
            uuid5(
                RUN_ID,
                (
                    f"event:{event['sequence']}:{event['type']}:"
                    f"{event.get('node_id', '')}"
                ),
            )
        )
        for event in result["events"]
    ]
    assert validation_codes(result, "run-trace.schema.json") == []
    assert persistence.logical_tool_invocations == 1


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "mutation",
    ["payload", "signature", "missing", "wrong_key"],
)
async def test_worker_rejects_untrusted_execution_envelopes(
    mutation: str,
) -> None:
    persistence = MemoryRuntimePersistence()
    worker_key = (
        b"different-worker-signing-key-32-bytes-minimum"
        if mutation == "wrong_key"
        else SIGNING_KEY
    )
    activities = RunExecutionActivities(
        signing_key=worker_key,
        persistence=persistence,
    )
    envelope = sign_execution_command(execution_command(), SIGNING_KEY)
    untrusted = deepcopy(envelope)
    if mutation == "payload":
        untrusted["payload"]["input"]["question"] = "modified"
    elif mutation == "signature":
        untrusted["signature"] = "0" * 64
    elif mutation == "missing":
        del untrusted["signature"]

    with pytest.raises(ValueError, match="execution_envelope_invalid"):
        await activities.execute_run(
            {
                "envelope": untrusted,
                "started_at": "2026-07-24T12:00:00Z",
            }
        )

    assert persistence.persistence_calls == 0
    assert persistence.logical_tool_invocations == 0
