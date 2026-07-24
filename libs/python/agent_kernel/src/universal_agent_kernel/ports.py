"""Replaceable execution ports owned by the Agent Kernel."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime
from typing import Any, Protocol

from universal_agent_kernel.domain import (
    ModelRequest,
    RunEvent,
    RunTrace,
    ToolRequest,
)


class ModelGatewayPort(Protocol):
    async def complete(self, request: ModelRequest) -> ToolRequest: ...


class ToolGatewayPort(Protocol):
    async def invoke(
        self,
        tool_id: str,
        arguments: Mapping[str, object],
    ) -> Mapping[str, object]: ...


class RunEventSink(Protocol):
    async def append(self, event: RunEvent) -> None: ...


class TraceStore(Protocol):
    async def save(self, trace: RunTrace) -> None: ...


class RedactionPolicyPort(Protocol):
    policy_id: str

    def redact(self, value: Any) -> Any: ...


class ClockPort(Protocol):
    def now(self) -> datetime: ...


class ExecutionPorts:
    def __init__(
        self,
        *,
        model_gateway: ModelGatewayPort,
        tool_gateway: ToolGatewayPort,
        event_sink: RunEventSink,
        trace_store: TraceStore,
        redaction_policy: RedactionPolicyPort,
        clock: ClockPort,
    ) -> None:
        self.model_gateway = model_gateway
        self.tool_gateway = tool_gateway
        self.event_sink = event_sink
        self.trace_store = trace_store
        self.redaction_policy = redaction_policy
        self.clock = clock
