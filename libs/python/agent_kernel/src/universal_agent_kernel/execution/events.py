"""Deterministic, causally linked RunEvent emission."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime
from typing import cast
from uuid import UUID, uuid5

from universal_agent_kernel.domain import EventType, ExecutionCommand, RunEvent
from universal_agent_kernel.ports import ExecutionPorts


class EventRecorder:
    def __init__(
        self,
        command: ExecutionCommand,
        ports: ExecutionPorts,
    ) -> None:
        self._command = command
        self._ports = ports
        self._events: list[RunEvent] = []

    @property
    def events(self) -> tuple[RunEvent, ...]:
        return tuple(self._events)

    async def emit(
        self,
        event_type: EventType,
        payload: Mapping[str, object],
        *,
        node_id: str | None = None,
        occurred_at: datetime | None = None,
    ) -> RunEvent:
        sequence = len(self._events) + 1
        event_id = uuid5(
            self._command.run_id,
            f"event:{sequence}:{event_type}:{node_id or ''}",
        )
        causation_id: UUID = (
            self._command.request_id
            if not self._events
            else self._events[-1].event_id
        )
        redacted = self._ports.redaction_policy.redact(dict(payload))
        event = RunEvent(
            event_id=event_id,
            run_id=self._command.run_id,
            sequence=sequence,
            type=event_type,
            occurred_at=occurred_at or self._ports.clock.now(),
            correlation_id=self._command.request_id,
            causation_id=causation_id,
            node_id=node_id,
            redaction_policy_id=self._ports.redaction_policy.policy_id,
            payload=cast(Mapping[str, object], redacted),
        )
        await self._ports.event_sink.append(event)
        self._events.append(event)
        return event
