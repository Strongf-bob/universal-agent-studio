from __future__ import annotations

import copy
import json
from collections.abc import Mapping
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, cast
from uuid import UUID, uuid5

import pytest
from universal_agent_kernel.contracts.validation import validation_codes
from universal_agent_kernel.domain import (
    ExecutionCommand,
    KernelExecutionError,
    RunEvent,
    RunTrace,
)
from universal_agent_kernel.execution.graph import AgentKernel
from universal_agent_kernel.models.fake import FakeModelGateway
from universal_agent_kernel.ports import ExecutionPorts
from universal_agent_kernel.redaction.policy import DefaultRedactionPolicy
from universal_agent_kernel.tools.calculator import CalculatorTool

ROOT = Path(__file__).parents[4]
GOLDEN_AGENT = (
    ROOT
    / "contracts"
    / "examples"
    / "v0.1.0"
    / "valid"
    / "agent.calculator.ru-en.json"
)
RUN_ID = UUID("22222222-2222-4222-8222-222222222222")
REQUEST_ID = UUID("11111111-1111-4111-8111-111111111111")


class RecordingEventSink:
    def __init__(self) -> None:
        self.events: list[RunEvent] = []

    async def append(self, event: RunEvent) -> None:
        self.events.append(event)


class RecordingTraceStore:
    def __init__(self) -> None:
        self.trace: RunTrace | None = None

    async def save(self, trace: RunTrace) -> None:
        self.trace = trace


class SteppingClock:
    def __init__(self) -> None:
        self.current = datetime(2026, 7, 24, 12, 0, tzinfo=UTC)

    def now(self) -> datetime:
        value = self.current
        self.current += timedelta(milliseconds=10)
        return value


def load_agent() -> dict[str, Any]:
    return cast(dict[str, Any], json.loads(GOLDEN_AGENT.read_text(encoding="utf-8")))


def command(agent_spec: Mapping[str, object]) -> ExecutionCommand:
    return ExecutionCommand(
        run_id=RUN_ID,
        request_id=REQUEST_ID,
        workspace_id=UUID("33333333-3333-4333-8333-333333333333"),
        project_id=UUID("44444444-4444-4444-8444-444444444444"),
        agent_version_id="calculator-v1",
        agent_version_digest="a" * 64,
        agent_spec=agent_spec,
        input={"question": "Сколько будет 19 × 23?"},
        locale="ru-RU",
    )


def ports() -> tuple[ExecutionPorts, RecordingEventSink, RecordingTraceStore]:
    events = RecordingEventSink()
    traces = RecordingTraceStore()
    return (
        ExecutionPorts(
            model_gateway=FakeModelGateway(),
            tool_gateway=CalculatorTool(),
            event_sink=events,
            trace_store=traces,
            redaction_policy=DefaultRedactionPolicy(),
            clock=SteppingClock(),
        ),
        events,
        traces,
    )


@pytest.mark.asyncio
async def test_golden_graph_emits_stable_events_and_result() -> None:
    execution_ports, events, traces = ports()

    outcome = await AgentKernel().execute(command(load_agent()), execution_ports)

    assert outcome.output == {"value": 437}
    assert [event.type for event in events.events] == [
        "run.started",
        "node.started",
        "model.requested",
        "model.completed",
        "tool.requested",
        "tool.completed",
        "node.completed",
        "run.completed",
    ]
    assert [event.event_id for event in events.events] == [
        uuid5(
            RUN_ID,
            f"event:{sequence}:{event.type}:{event.node_id or ''}",
        )
        for sequence, event in enumerate(events.events, start=1)
    ]
    assert traces.trace == outcome.trace
    assert outcome.trace.output == {"value": 437}
    assert validation_codes(
        outcome.trace.to_document(),
        "run-trace.schema.json",
    ) == []


@pytest.mark.asyncio
async def test_final_output_must_match_interface_schema() -> None:
    agent = copy.deepcopy(load_agent())
    agent["interface"]["result_schema"] = {
        "type": "object",
        "required": ["answer"],
        "properties": {"answer": {"type": "string"}},
        "additionalProperties": False,
    }
    execution_ports, _, _ = ports()

    with pytest.raises(KernelExecutionError) as error:
        await AgentKernel().execute(command(agent), execution_ports)

    assert error.value.code == "output_schema_validation_failed"


@pytest.mark.asyncio
async def test_unknown_node_kind_fails_closed() -> None:
    agent = copy.deepcopy(load_agent())
    agent["nodes"][1]["kind"] = "router"
    execution_ports, _, _ = ports()

    with pytest.raises(KernelExecutionError) as error:
        await AgentKernel().execute(command(agent), execution_ports)

    assert error.value.code == "agent_spec_invalid"
