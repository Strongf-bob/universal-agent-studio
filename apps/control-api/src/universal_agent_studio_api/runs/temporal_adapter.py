"""Temporal implementation hidden behind DurableExecutionPort."""

from __future__ import annotations

from uuid import UUID

from temporalio.client import Client, WorkflowExecutionStatus
from temporalio.common import WorkflowIDConflictPolicy, WorkflowIDReusePolicy
from temporalio.service import RPCError
from universal_agent_kernel.domain import ExecutionCommand
from universal_agent_kernel.execution.envelope import sign_execution_command

from universal_agent_studio_api.runs.durable import (
    CancellationStatus,
    DurableStatus,
)

DEFAULT_TASK_QUEUE = "uas-runtime-v1"


def workflow_id(run_id: UUID) -> str:
    return f"uas-run-{run_id}"


class TemporalDurableExecutionAdapter:
    def __init__(
        self,
        client: Client,
        *,
        signing_key: bytes,
        task_queue: str = DEFAULT_TASK_QUEUE,
    ) -> None:
        self.client = client
        self.signing_key = signing_key
        self.task_queue = task_queue

    async def start_run(self, command: ExecutionCommand) -> str:
        durable_id = workflow_id(command.run_id)
        await self.client.start_workflow(
            "AgentRunWorkflow",
            sign_execution_command(command, self.signing_key),
            id=durable_id,
            task_queue=self.task_queue,
            id_reuse_policy=WorkflowIDReusePolicy.REJECT_DUPLICATE,
            id_conflict_policy=WorkflowIDConflictPolicy.USE_EXISTING,
        )
        return durable_id

    async def request_cancel(self, run_id: UUID) -> CancellationStatus:
        handle = self.client.get_workflow_handle(workflow_id(run_id))
        try:
            description = await handle.describe()
            if description.status in {
                WorkflowExecutionStatus.COMPLETED,
                WorkflowExecutionStatus.FAILED,
                WorkflowExecutionStatus.CANCELED,
                WorkflowExecutionStatus.TERMINATED,
                WorkflowExecutionStatus.TIMED_OUT,
            }:
                return "already_terminal"
            await handle.signal("request_cancel")
        except RPCError:
            return "not_found"
        return "requested"

    async def describe(self, run_id: UUID) -> DurableStatus:
        try:
            status = (
                await self.client.get_workflow_handle(workflow_id(run_id)).describe()
            ).status
        except RPCError:
            return "not_found"
        statuses: dict[WorkflowExecutionStatus, DurableStatus] = {
            WorkflowExecutionStatus.RUNNING: "running",
            WorkflowExecutionStatus.COMPLETED: "completed",
            WorkflowExecutionStatus.FAILED: "failed",
            WorkflowExecutionStatus.CANCELED: "cancelled",
            WorkflowExecutionStatus.TERMINATED: "cancelled",
            WorkflowExecutionStatus.TIMED_OUT: "failed",
            WorkflowExecutionStatus.CONTINUED_AS_NEW: "running",
        }
        if status is None:
            return "queued"
        return statuses.get(status, "queued")
