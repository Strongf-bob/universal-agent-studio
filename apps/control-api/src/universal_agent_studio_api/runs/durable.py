"""Product-owned durable execution port."""

from __future__ import annotations

from typing import Literal, Protocol
from uuid import UUID

from universal_agent_kernel.domain import ExecutionCommand

DurableStatus = Literal[
    "queued",
    "running",
    "completed",
    "failed",
    "cancelled",
    "not_found",
]
CancellationStatus = Literal["requested", "not_found", "already_terminal"]


class DurableExecutionPort(Protocol):
    async def start_run(self, command: ExecutionCommand) -> str: ...

    async def request_cancel(self, run_id: UUID) -> CancellationStatus: ...

    async def describe(self, run_id: UUID) -> DurableStatus: ...
