from __future__ import annotations

from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

import pytest
import pytest_asyncio
from conftest import MemoryAgentVersionPersistence, MemoryAuthStore
from httpx import ASGITransport, AsyncClient
from universal_agent_kernel.domain import ExecutionCommand
from universal_agent_platform_store.repositories.runs import IdempotencyConflict
from universal_agent_platform_store.scope import RequestScope
from universal_agent_studio_api.main import create_app
from universal_agent_studio_api.runs.durable import (
    CancellationStatus,
    DurableStatus,
)
from universal_agent_studio_api.runs.service import (
    RunCreateData,
    StoredRun,
)
from universal_agent_studio_api.settings import Settings

ROOT = Path(__file__).parents[3]
GOLDEN_AGENT = (
    ROOT / "contracts" / "examples" / "v0.1.0" / "valid" / "agent.calculator.ru-en.json"
)


class MemoryRunPersistence:
    def __init__(self) -> None:
        self.runs: dict[tuple[UUID, UUID, UUID], StoredRun] = {}
        self.idempotency: dict[tuple[UUID, UUID, str], tuple[str, UUID]] = {}
        self.events: dict[UUID, list[dict[str, Any]]] = {}
        self.traces: dict[UUID, dict[str, Any]] = {}
        self.fail_durable_id_write = False

    async def create_idempotent(
        self,
        *,
        scope: RequestScope,
        data: RunCreateData,
        request_digest: str,
    ) -> tuple[StoredRun, bool]:
        workspace_id, project_id = scope.tenant_ids()
        key = (workspace_id, project_id, data.idempotency_key)
        existing = self.idempotency.get(key)
        if existing is not None:
            if existing[0] != request_digest:
                raise IdempotencyConflict("idempotency_key_reused")
            return self.runs[(workspace_id, project_id, existing[1])], False
        run = StoredRun(
            id=uuid4(),
            request_id=data.request_id,
            workspace_id=workspace_id,
            project_id=project_id,
            agent_version_internal_id=data.agent_version_internal_id,
            agent_version_id=data.agent_version_id,
            agent_version_digest=data.agent_version_digest,
            status="queued",
            locale=data.locale,
            input=dict(data.input),
            output=None,
            durable_execution_id=None,
            cancel_requested=False,
        )
        self.runs[(workspace_id, project_id, run.id)] = run
        self.idempotency[key] = (request_digest, run.id)
        return run, True

    async def set_durable_execution_id(
        self,
        *,
        scope: RequestScope,
        run_id: UUID,
        durable_execution_id: str,
    ) -> None:
        if self.fail_durable_id_write:
            raise RuntimeError("database_write_failed")
        run = await self.get_run(scope=scope, run_id=run_id)
        assert run is not None
        self._replace(run, durable_execution_id=durable_execution_id)

    async def get_run(
        self,
        *,
        scope: RequestScope,
        run_id: UUID,
    ) -> StoredRun | None:
        workspace_id, project_id = scope.tenant_ids()
        return self.runs.get((workspace_id, project_id, run_id))

    async def request_cancel(
        self,
        *,
        scope: RequestScope,
        run_id: UUID,
    ) -> StoredRun | None:
        run = await self.get_run(scope=scope, run_id=run_id)
        if run is None:
            return None
        return self._replace(run, cancel_requested=True)

    async def list_events(
        self,
        *,
        scope: RequestScope,
        run_id: UUID,
        after_sequence: int,
    ) -> list[dict[str, Any]]:
        if await self.get_run(scope=scope, run_id=run_id) is None:
            return []
        return [
            event
            for event in self.events.get(run_id, [])
            if int(event["sequence"]) > after_sequence
        ]

    async def get_trace(
        self,
        *,
        scope: RequestScope,
        run_id: UUID,
    ) -> dict[str, Any] | None:
        if await self.get_run(scope=scope, run_id=run_id) is None:
            return None
        return self.traces.get(run_id)

    async def finalize_start_failure(
        self,
        *,
        scope: RequestScope,
        run: StoredRun,
        error_code: str,
    ) -> None:
        del scope, error_code
        self._replace(run, status="failed", output={})

    def _replace(self, run: StoredRun, **changes: Any) -> StoredRun:
        changed = StoredRun(**{**run.__dict__, **changes})
        self.runs[(run.workspace_id, run.project_id, run.id)] = changed
        return changed


class FakeDurableExecution:
    def __init__(self) -> None:
        self.commands: list[ExecutionCommand] = []
        self.cancelled: list[UUID] = []
        self.fail_start = False

    async def start_run(self, command: ExecutionCommand) -> str:
        if self.fail_start:
            raise RuntimeError("temporal_unavailable")
        self.commands.append(command)
        return f"uas-run-{command.run_id}"

    async def request_cancel(self, run_id: UUID) -> CancellationStatus:
        self.cancelled.append(run_id)
        return "requested"

    async def describe(self, run_id: UUID) -> DurableStatus:
        del run_id
        return "running"


@pytest.fixture
def run_persistence() -> MemoryRunPersistence:
    return MemoryRunPersistence()


@pytest.fixture
def durable_execution() -> FakeDurableExecution:
    return FakeDurableExecution()


@pytest_asyncio.fixture
async def run_client(
    auth_store: MemoryAuthStore,
    agent_persistence: MemoryAgentVersionPersistence,
    run_persistence: MemoryRunPersistence,
    durable_execution: FakeDurableExecution,
) -> AsyncIterator[AsyncClient]:
    app = create_app(
        auth_store=auth_store,
        agent_persistence=agent_persistence,
        run_persistence=run_persistence,
        durable_execution=durable_execution,
        settings=Settings(
            allowed_hosts=["testserver"],
            allowed_origins=["http://testserver"],
            secure_cookies=False,
            max_request_bytes=16_384,
            sse_poll_interval_seconds=0.001,
            sse_heartbeat_seconds=0.001,
            sse_max_polls=2,
        ),
    )
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
        headers={"Origin": "http://testserver"},
    ) as client:
        yield client


async def _bootstrap_and_activate(client: AsyncClient) -> tuple[str, dict[str, Any]]:
    bootstrap = await client.post(
        "/api/v1/bootstrap/owner",
        json={
            "login_name": "owner",
            "password": "correct horse battery staple",
            "preferred_locale": "ru-RU",
        },
    )
    csrf = bootstrap.json()["csrf_token"]
    imported = await client.post(
        "/api/v1/agent-versions/import",
        content=GOLDEN_AGENT.read_bytes(),
        headers={"Content-Type": "application/json", "X-CSRF-Token": csrf},
    )
    version = imported.json()
    activated = await client.post(
        "/api/v1/agents/calculator-agent/active-version",
        json={
            "version_id": version["version_id"],
            "expected_previous_version_id": None,
        },
        headers={"X-CSRF-Token": csrf},
    )
    assert activated.status_code == 200
    return csrf, version


def _run_request(version: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": "0.1.0",
        "request_id": "11111111-1111-4111-8111-111111111111",
        "agent_version_id": version["version_id"],
        "agent_version_digest": version["digest"],
        "idempotency_key": "browser-run-00000001",
        "input": {"question": "Сколько будет 19 × 23?"},
        "locale": "ru-RU",
    }


@pytest.mark.asyncio
async def test_run_creation_is_immediate_and_idempotent(
    run_client: AsyncClient,
    durable_execution: FakeDurableExecution,
) -> None:
    csrf, version = await _bootstrap_and_activate(run_client)
    body = _run_request(version)

    first = await run_client.post(
        "/api/v1/runs",
        json=body,
        headers={"X-CSRF-Token": csrf},
    )
    repeated = await run_client.post(
        "/api/v1/runs",
        json=body,
        headers={"X-CSRF-Token": csrf},
    )
    changed = await run_client.post(
        "/api/v1/runs",
        json={**body, "input": {"question": "different"}},
        headers={"X-CSRF-Token": csrf},
    )

    assert first.status_code == 201
    assert first.json()["status"] == "queued"
    assert repeated.status_code == 200
    assert repeated.json()["run_id"] == first.json()["run_id"]
    assert repeated.json()["reused"] is True
    assert changed.status_code == 409
    assert changed.json()["code"] == "idempotency_key_reused"
    assert len(durable_execution.commands) == 1
    assert durable_execution.commands[0].agent_version_id == version["version_id"]


@pytest.mark.asyncio
async def test_run_rejects_inactive_or_digest_mismatched_version(
    run_client: AsyncClient,
) -> None:
    csrf, version = await _bootstrap_and_activate(run_client)
    body = _run_request(version)

    mismatch = await run_client.post(
        "/api/v1/runs",
        json={**body, "agent_version_digest": "0" * 64},
        headers={"X-CSRF-Token": csrf},
    )
    inactive = await run_client.post(
        "/api/v1/runs",
        json={**body, "agent_version_id": "calculator-agent-v999"},
        headers={"X-CSRF-Token": csrf},
    )

    assert mismatch.status_code == 409
    assert mismatch.json()["code"] == "agent_version_digest_mismatch"
    assert inactive.status_code == 409
    assert inactive.json()["code"] == "agent_version_not_active"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "invalid_input",
    [
        {},
        {"question": ""},
        {"question": 437},
        {"question": "19 × 23", "unexpected": True},
    ],
)
async def test_run_rejects_input_outside_the_active_agent_interface(
    run_client: AsyncClient,
    invalid_input: dict[str, Any],
) -> None:
    csrf, version = await _bootstrap_and_activate(run_client)

    response = await run_client.post(
        "/api/v1/runs",
        json={**_run_request(version), "input": invalid_input},
        headers={"X-CSRF-Token": csrf},
    )

    assert response.status_code == 422
    assert response.json()["code"] == "run_input_invalid"


@pytest.mark.asyncio
async def test_run_read_cancel_and_trace_state(
    run_client: AsyncClient,
    durable_execution: FakeDurableExecution,
) -> None:
    csrf, version = await _bootstrap_and_activate(run_client)
    created = await run_client.post(
        "/api/v1/runs",
        json=_run_request(version),
        headers={"X-CSRF-Token": csrf},
    )
    run_id = created.json()["run_id"]

    fetched = await run_client.get(f"/api/v1/runs/{run_id}")
    early_trace = await run_client.get(f"/api/v1/runs/{run_id}/trace")
    cancelled = await run_client.post(
        f"/api/v1/runs/{run_id}/cancel",
        headers={"X-CSRF-Token": csrf},
    )

    assert fetched.status_code == 200
    assert fetched.json()["run_id"] == run_id
    assert early_trace.status_code == 409
    assert early_trace.json()["code"] == "run_not_terminal"
    assert cancelled.status_code == 202
    assert cancelled.json()["status"] == "requested"
    assert durable_execution.cancelled == [UUID(run_id)]


@pytest.mark.asyncio
async def test_durable_start_failure_is_safely_finalized(
    run_client: AsyncClient,
    durable_execution: FakeDurableExecution,
    run_persistence: MemoryRunPersistence,
) -> None:
    csrf, version = await _bootstrap_and_activate(run_client)
    durable_execution.fail_start = True

    response = await run_client.post(
        "/api/v1/runs",
        json=_run_request(version),
        headers={"X-CSRF-Token": csrf},
    )

    assert response.status_code == 503
    assert response.json()["code"] == "durable_execution_unavailable"
    assert next(iter(run_persistence.runs.values())).status == "failed"


@pytest.mark.asyncio
async def test_retry_resumes_dispatch_after_durable_id_write_crash(
    run_client: AsyncClient,
    durable_execution: FakeDurableExecution,
    run_persistence: MemoryRunPersistence,
) -> None:
    csrf, version = await _bootstrap_and_activate(run_client)
    body = _run_request(version)
    run_persistence.fail_durable_id_write = True

    interrupted = await run_client.post(
        "/api/v1/runs",
        json=body,
        headers={"X-CSRF-Token": csrf},
    )
    assert interrupted.status_code == 503
    assert next(iter(run_persistence.runs.values())).status == "queued"

    run_persistence.fail_durable_id_write = False
    resumed = await run_client.post(
        "/api/v1/runs",
        json=body,
        headers={"X-CSRF-Token": csrf},
    )

    assert resumed.status_code == 200
    assert resumed.json()["reused"] is True
    assert len(durable_execution.commands) == 2
    assert next(iter(run_persistence.runs.values())).durable_execution_id


@pytest.mark.asyncio
async def test_terminal_trace_is_returned_from_persistence(
    run_client: AsyncClient,
    run_persistence: MemoryRunPersistence,
) -> None:
    csrf, version = await _bootstrap_and_activate(run_client)
    created = await run_client.post(
        "/api/v1/runs",
        json=_run_request(version),
        headers={"X-CSRF-Token": csrf},
    )
    run = next(iter(run_persistence.runs.values()))
    run_persistence._replace(run, status="completed", output={"value": 437})
    run_persistence.traces[run.id] = {
        "schema_version": "0.1.0",
        "run_id": str(run.id),
        "status": "completed",
        "output": {"value": 437},
    }

    response = await run_client.get(
        f"/api/v1/runs/{created.json()['run_id']}/trace"
    )

    assert response.status_code == 200
    assert response.json()["output"] == {"value": 437}
