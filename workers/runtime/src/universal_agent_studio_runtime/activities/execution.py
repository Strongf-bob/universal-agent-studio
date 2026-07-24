"""Trusted execution and cancellation activities."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from typing import Any, cast
from uuid import UUID, uuid5

from temporalio import activity
from universal_agent_kernel.domain import ExecutionCommand, RunEvent
from universal_agent_kernel.execution.envelope import verify_execution_envelope
from universal_agent_kernel.execution.graph import AgentKernel
from universal_agent_kernel.models.fake import FakeModelGateway
from universal_agent_kernel.ports import ExecutionPorts
from universal_agent_kernel.redaction.policy import DefaultRedactionPolicy
from universal_agent_platform_store.scope import RequestScope

from universal_agent_studio_runtime.activities.events import (
    IdempotentCalculatorGateway,
    PersistedEventSink,
    PersistedTraceStore,
    RuntimePersistence,
)


def _parse_timestamp(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed


def _timestamp(value: datetime) -> str:
    return value.isoformat().replace("+00:00", "Z")


class SteppingActivityClock:
    def __init__(self, started_at: datetime) -> None:
        self.current = started_at

    def now(self) -> datetime:
        value = self.current
        self.current += timedelta(milliseconds=10)
        return value


def _scope(command: ExecutionCommand) -> RequestScope:
    return RequestScope(
        workspace_id=command.workspace_id,
        project_id=command.project_id,
    )


class RunExecutionActivities:
    def __init__(
        self,
        *,
        signing_key: bytes,
        persistence: RuntimePersistence,
        deterministic_delay_seconds: float = 0,
    ) -> None:
        self.signing_key = signing_key
        self.persistence = persistence
        self.deterministic_delay_seconds = deterministic_delay_seconds

    def _trusted_command(self, activity_input: dict[str, Any]) -> ExecutionCommand:
        envelope = activity_input.get("envelope")
        if not isinstance(envelope, dict):
            raise ValueError("execution_envelope_invalid")
        return verify_execution_envelope(envelope, self.signing_key)

    @activity.defn(name="execute_run")
    async def execute_run(
        self,
        activity_input: dict[str, Any],
    ) -> dict[str, Any]:
        command = self._trusted_command(activity_input)
        started_at_value = activity_input.get("started_at")
        if not isinstance(started_at_value, str):
            raise ValueError("execution_started_at_invalid")
        started_at = _parse_timestamp(started_at_value)
        activity.heartbeat("execution_verified")
        if self.deterministic_delay_seconds > 0:
            await asyncio.sleep(self.deterministic_delay_seconds)
        scope = _scope(command)
        tool_node = next(
            (
                node
                for node in cast(
                    list[dict[str, Any]],
                    command.agent_spec["nodes"],
                )
                if node.get("kind") == "tool"
            ),
            None,
        )
        if tool_node is None or not isinstance(tool_node.get("id"), str):
            raise ValueError("tool_node_missing")
        ports = ExecutionPorts(
            model_gateway=FakeModelGateway(),
            tool_gateway=IdempotentCalculatorGateway(
                self.persistence,
                scope,
                command.run_id,
                cast(str, tool_node["id"]),
            ),
            event_sink=PersistedEventSink(
                self.persistence,
                scope,
                command.run_id,
            ),
            trace_store=PersistedTraceStore(
                self.persistence,
                scope,
                command.run_id,
            ),
            redaction_policy=DefaultRedactionPolicy(),
            clock=SteppingActivityClock(started_at),
        )
        outcome = await AgentKernel().execute(command, ports)
        return outcome.trace.to_document()

    @activity.defn(name="finalize_cancelled_run")
    async def finalize_cancelled_run(
        self,
        activity_input: dict[str, Any],
    ) -> dict[str, Any]:
        return await self._finalize_terminal_run(
            activity_input,
            status="cancelled",
        )

    @activity.defn(name="finalize_failed_run")
    async def finalize_failed_run(
        self,
        activity_input: dict[str, Any],
    ) -> dict[str, Any]:
        return await self._finalize_terminal_run(
            activity_input,
            status="failed",
        )

    async def _finalize_terminal_run(
        self,
        activity_input: dict[str, Any],
        *,
        status: str,
    ) -> dict[str, Any]:
        command = self._trusted_command(activity_input)
        started_at_value = activity_input.get("started_at")
        if not isinstance(started_at_value, str):
            raise ValueError("execution_started_at_invalid")
        started_at = _parse_timestamp(started_at_value)
        scope = _scope(command)
        events = await self.persistence.list_events(
            scope=scope,
            run_id=command.run_id,
        )
        if not events:
            started_event = RunEvent(
                event_id=uuid5(command.run_id, "event:1:run.started:"),
                run_id=command.run_id,
                sequence=1,
                type="run.started",
                occurred_at=started_at,
                correlation_id=command.request_id,
                causation_id=command.request_id,
                node_id=None,
                redaction_policy_id="default-redaction",
                payload={"agent_version_id": command.agent_version_id},
            ).to_document()
            await self.persistence.append_event(
                scope=scope,
                run_id=command.run_id,
                document=started_event,
            )
            events.append(started_event)

        last = events[-1]
        terminal_type = f"run.{status}"
        if last["type"] == terminal_type:
            terminal_event = last
        else:
            sequence = int(last["sequence"]) + 1
            terminal_event = RunEvent(
                event_id=uuid5(
                    command.run_id,
                    f"event:{sequence}:{terminal_type}:",
                ),
                run_id=command.run_id,
                sequence=sequence,
                type=cast(Any, terminal_type),
                occurred_at=started_at + timedelta(milliseconds=sequence * 10),
                correlation_id=command.request_id,
                causation_id=UUID(str(last["event_id"])),
                node_id=None,
                redaction_policy_id="default-redaction",
                payload=(
                    {"status": "cancelled"}
                    if status == "cancelled"
                    else {"code": "execution_failed"}
                ),
            ).to_document()
            await self.persistence.append_event(
                scope=scope,
                run_id=command.run_id,
                document=terminal_event,
            )
            events.append(terminal_event)

        completed_at = str(terminal_event["occurred_at"])
        trace: dict[str, Any] = {
            "schema_version": "0.1.0",
            "run_id": str(command.run_id),
            "request_id": str(command.request_id),
            "agent_version_id": command.agent_version_id,
            "agent_version_digest": command.agent_version_digest,
            "status": status,
            "started_at": _timestamp(started_at),
            "completed_at": completed_at,
            "input": DefaultRedactionPolicy().redact(dict(command.input)),
            "output": {},
            "events": events,
            "node_executions": [],
            "provenance": {
                "model_resolutions": [],
                "tool_resolutions": [],
                "redaction_policy_id": "default-redaction",
            },
            "metrics": {
                "duration_ms": max(
                    0,
                    round(
                        (_parse_timestamp(completed_at) - started_at).total_seconds()
                        * 1000
                    ),
                ),
                "input_tokens": 0,
                "output_tokens": 0,
                "tool_calls": 0,
                "cost": {"amount": 0, "currency": "USD"},
            },
        }
        if status == "failed":
            trace["error"] = {
                "code": "execution_failed",
                "message_key": "errors.execution_failed",
                "retryable": False,
                "details": {},
            }
        await self.persistence.finalize_trace(
            scope=scope,
            run_id=command.run_id,
            document=trace,
        )
        return trace
