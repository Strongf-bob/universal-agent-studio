"""Deterministic one-workflow-per-run orchestration."""

from __future__ import annotations

import asyncio
from datetime import timedelta
from typing import Any, cast

from temporalio import workflow
from temporalio.common import RetryPolicy
from temporalio.workflow import ActivityCancellationType


@workflow.defn(name="AgentRunWorkflow")
class AgentRunWorkflow:
    def __init__(self) -> None:
        self.cancel_requested = False

    @workflow.signal(name="request_cancel")
    async def request_cancel(self) -> None:
        self.cancel_requested = True

    @workflow.run
    async def run(self, envelope: dict[str, Any]) -> dict[str, Any]:
        started_at = workflow.now().isoformat().replace("+00:00", "Z")
        activity_input = {
            "envelope": envelope,
            "started_at": started_at,
        }
        if self.cancel_requested:
            return await self._finalize_cancelled(activity_input)

        execution = workflow.start_activity(
            "execute_run",
            activity_input,
            result_type=dict,
            start_to_close_timeout=timedelta(minutes=2),
            heartbeat_timeout=timedelta(seconds=5),
            retry_policy=RetryPolicy(
                initial_interval=timedelta(seconds=1),
                backoff_coefficient=2,
                maximum_interval=timedelta(seconds=5),
                maximum_attempts=3,
            ),
            cancellation_type=ActivityCancellationType.TRY_CANCEL,
        )
        cancellation = asyncio.create_task(
            workflow.wait_condition(lambda: self.cancel_requested)
        )
        done, _ = await workflow.wait(
            [execution, cancellation],
            return_when=asyncio.FIRST_COMPLETED,
        )
        if execution in done:
            cancellation.cancel()
            return cast(dict[str, Any], await execution)

        execution.cancel()
        try:
            await execution
        except (asyncio.CancelledError, Exception):
            pass
        return await self._finalize_cancelled(activity_input)

    async def _finalize_cancelled(
        self,
        activity_input: dict[str, Any],
    ) -> dict[str, Any]:
        return cast(
            dict[str, Any],
            await workflow.execute_activity(
                "finalize_cancelled_run",
                activity_input,
                result_type=dict,
                start_to_close_timeout=timedelta(seconds=30),
                retry_policy=RetryPolicy(maximum_attempts=3),
            ),
        )
