"""Provider-independent immutable domain values for agent execution."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from typing import Literal
from uuid import UUID

EventType = Literal[
    "run.started",
    "node.started",
    "model.requested",
    "model.completed",
    "tool.requested",
    "tool.completed",
    "approval.required",
    "approval.resolved",
    "node.failed",
    "node.completed",
    "run.completed",
    "run.failed",
    "run.cancelled",
]


def _timestamp(value: datetime) -> str:
    return value.isoformat().replace("+00:00", "Z")


class KernelExecutionError(RuntimeError):
    def __init__(self, code: str, *, node_id: str | None = None) -> None:
        self.code = code
        self.node_id = node_id
        super().__init__(code)


class ModelExecutionError(KernelExecutionError):
    pass


class ToolExecutionError(KernelExecutionError):
    pass


@dataclass(frozen=True)
class ExecutionCommand:
    run_id: UUID
    request_id: UUID
    workspace_id: UUID
    project_id: UUID
    agent_version_id: str
    agent_version_digest: str
    agent_spec: Mapping[str, object]
    input: Mapping[str, object]
    locale: str


@dataclass(frozen=True)
class ModelRequest:
    profile_id: str
    model: str
    input: Mapping[str, object]
    locale: str


@dataclass(frozen=True)
class ToolRequest:
    tool_id: str
    arguments: Mapping[str, object]


@dataclass(frozen=True)
class RunEvent:
    event_id: UUID
    run_id: UUID
    sequence: int
    type: EventType
    occurred_at: datetime
    correlation_id: UUID
    causation_id: UUID
    node_id: str | None
    redaction_policy_id: str
    payload: Mapping[str, object]

    def to_document(self) -> dict[str, object]:
        document: dict[str, object] = {
            "schema_version": "0.1.0",
            "event_id": str(self.event_id),
            "run_id": str(self.run_id),
            "sequence": self.sequence,
            "type": self.type,
            "occurred_at": _timestamp(self.occurred_at),
            "correlation_id": str(self.correlation_id),
            "causation_id": str(self.causation_id),
            "redaction_policy_id": self.redaction_policy_id,
            "payload": dict(self.payload),
        }
        if self.node_id is not None:
            document["node_id"] = self.node_id
        return document


@dataclass(frozen=True)
class NodeExecution:
    node_id: str
    status: Literal["completed", "failed", "cancelled"]
    started_at: datetime
    completed_at: datetime
    duration_ms: int
    input: Mapping[str, object]
    output: Mapping[str, object]
    attempt: int = 1

    def to_document(self) -> dict[str, object]:
        return {
            "node_id": self.node_id,
            "attempt": self.attempt,
            "status": self.status,
            "started_at": _timestamp(self.started_at),
            "completed_at": _timestamp(self.completed_at),
            "duration_ms": self.duration_ms,
            "input": dict(self.input),
            "output": dict(self.output),
        }


@dataclass(frozen=True)
class RunTrace:
    run_id: UUID
    request_id: UUID
    agent_version_id: str
    agent_version_digest: str
    status: Literal["completed", "failed", "cancelled"]
    started_at: datetime
    completed_at: datetime
    input: Mapping[str, object]
    output: Mapping[str, object]
    events: tuple[RunEvent, ...]
    node_executions: tuple[NodeExecution, ...]
    provenance: Mapping[str, object]
    metrics: Mapping[str, object]

    def to_document(self) -> dict[str, object]:
        return {
            "schema_version": "0.1.0",
            "run_id": str(self.run_id),
            "request_id": str(self.request_id),
            "agent_version_id": self.agent_version_id,
            "agent_version_digest": self.agent_version_digest,
            "status": self.status,
            "started_at": _timestamp(self.started_at),
            "completed_at": _timestamp(self.completed_at),
            "input": dict(self.input),
            "output": dict(self.output),
            "events": [event.to_document() for event in self.events],
            "node_executions": [
                execution.to_document()
                for execution in self.node_executions
            ],
            "provenance": dict(self.provenance),
            "metrics": dict(self.metrics),
        }


@dataclass(frozen=True)
class RunOutcome:
    output: Mapping[str, object]
    trace: RunTrace
