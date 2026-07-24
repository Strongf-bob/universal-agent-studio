from __future__ import annotations

import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any
from uuid import UUID

from universal_agent_kernel.contracts.canonical import content_digest
from universal_agent_kernel.domain import ExecutionCommand
from universal_agent_platform_store.scope import RequestScope

ROOT = Path(__file__).parents[2]
GOLDEN_AGENT = (
    ROOT / "contracts" / "examples" / "v0.1.0" / "valid" / "agent.calculator.ru-en.json"
)
RUN_ID = UUID("22222222-2222-4222-8222-222222222222")
REQUEST_ID = UUID("11111111-1111-4111-8111-111111111111")
WORKSPACE_ID = UUID("33333333-3333-4333-8333-333333333333")
PROJECT_ID = UUID("44444444-4444-4444-8444-444444444444")
OWNER_ID = UUID("55555555-5555-4555-8555-555555555555")
SIGNING_KEY = b"slice-1-test-signing-key-with-32-bytes-minimum"


def execution_command() -> ExecutionCommand:
    agent_spec = json.loads(GOLDEN_AGENT.read_bytes())
    return ExecutionCommand(
        run_id=RUN_ID,
        request_id=REQUEST_ID,
        workspace_id=WORKSPACE_ID,
        project_id=PROJECT_ID,
        agent_version_id="calculator-agent-v1",
        agent_version_digest=content_digest(agent_spec),
        agent_spec=agent_spec,
        input={"question": "Сколько будет 19 × 23?"},
        locale="ru-RU",
    )


class MemoryRuntimePersistence:
    def __init__(self) -> None:
        self.events: dict[int, dict[str, Any]] = {}
        self.trace: dict[str, Any] | None = None
        self.tool_results: dict[str, dict[str, object]] = {}
        self.logical_tool_invocations = 0
        self.persistence_calls = 0

    async def append_event(
        self,
        *,
        scope: RequestScope,
        run_id: UUID,
        document: dict[str, Any],
    ) -> None:
        assert scope.tenant_ids() == (WORKSPACE_ID, PROJECT_ID)
        assert run_id == RUN_ID
        self.persistence_calls += 1
        sequence = int(document["sequence"])
        existing = self.events.get(sequence)
        if existing is not None:
            assert existing == document
            return
        self.events[sequence] = document

    async def finalize_trace(
        self,
        *,
        scope: RequestScope,
        run_id: UUID,
        document: dict[str, Any],
    ) -> None:
        assert scope.tenant_ids() == (WORKSPACE_ID, PROJECT_ID)
        assert run_id == RUN_ID
        self.persistence_calls += 1
        if self.trace is not None:
            assert self.trace == document
            return
        self.trace = document

    async def list_events(
        self,
        *,
        scope: RequestScope,
        run_id: UUID,
    ) -> list[dict[str, Any]]:
        assert scope.tenant_ids() == (WORKSPACE_ID, PROJECT_ID)
        assert run_id == RUN_ID
        self.persistence_calls += 1
        return [self.events[key] for key in sorted(self.events)]

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
        del scope, run_id, node_id, tool_id, arguments
        existing = self.tool_results.get(invocation_key)
        if existing is not None:
            return existing
        self.logical_tool_invocations += 1
        result: dict[str, object] = {"value": 437}
        self.tool_results[invocation_key] = result
        return result
