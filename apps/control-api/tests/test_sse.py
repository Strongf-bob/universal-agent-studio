from __future__ import annotations

import json
from typing import Any

import pytest
from httpx import AsyncClient
from test_runs_api import (
    MemoryRunPersistence,
    _bootstrap_and_activate,
    _run_request,
    durable_execution,
    run_client,
    run_persistence,
)

__all__ = ["durable_execution", "run_client", "run_persistence"]


def _event(run_id: str, sequence: int, event_type: str) -> dict[str, Any]:
    return {
        "schema_version": "0.1.0",
        "event_id": f"00000000-0000-5000-8000-{sequence:012d}",
        "run_id": run_id,
        "sequence": sequence,
        "type": event_type,
        "occurred_at": "2026-07-24T12:00:00Z",
        "correlation_id": "11111111-1111-4111-8111-111111111111",
        "causation_id": "11111111-1111-4111-8111-111111111111",
        "redaction_policy_id": "default-redaction",
        "payload": {},
    }


@pytest.mark.asyncio
async def test_sse_resumes_after_last_event_and_closes_on_terminal(
    run_client: AsyncClient,
    run_persistence: MemoryRunPersistence,
) -> None:
    csrf, version = await _bootstrap_and_activate(run_client)
    created = await run_client.post(
        "/api/v1/runs",
        json=_run_request(version),
        headers={"X-CSRF-Token": csrf},
    )
    run_id = created.json()["run_id"]
    run_uuid = next(iter(run_persistence.runs.values())).id
    run_persistence.events[run_uuid] = [
        _event(run_id, 1, "run.started"),
        _event(run_id, 2, "node.started"),
        _event(run_id, 3, "run.completed"),
    ]
    run = next(iter(run_persistence.runs.values()))
    run_persistence._replace(run, status="completed", output={"value": 437})

    response = await run_client.get(
        f"/api/v1/runs/{run_id}/events",
        headers={"Last-Event-ID": "1"},
    )

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    assert "id: 1\n" not in response.text
    assert "id: 2\nevent: node.started\n" in response.text
    assert "id: 3\nevent: run.completed\n" in response.text
    data_lines = [
        line.removeprefix("data: ")
        for line in response.text.splitlines()
        if line.startswith("data: ")
    ]
    assert [json.loads(line)["sequence"] for line in data_lines] == [2, 3]


@pytest.mark.asyncio
async def test_sse_sends_heartbeat_while_waiting(
    run_client: AsyncClient,
) -> None:
    csrf, version = await _bootstrap_and_activate(run_client)
    created = await run_client.post(
        "/api/v1/runs",
        json=_run_request(version),
        headers={"X-CSRF-Token": csrf},
    )

    response = await run_client.get(f"/api/v1/runs/{created.json()['run_id']}/events")

    assert response.status_code == 200
    assert ": heartbeat\n\n" in response.text


@pytest.mark.asyncio
async def test_sse_rejects_invalid_last_event_id(
    run_client: AsyncClient,
) -> None:
    csrf, version = await _bootstrap_and_activate(run_client)
    created = await run_client.post(
        "/api/v1/runs",
        json=_run_request(version),
        headers={"X-CSRF-Token": csrf},
    )

    response = await run_client.get(
        f"/api/v1/runs/{created.json()['run_id']}/events",
        headers={"Last-Event-ID": "not-a-sequence"},
    )

    assert response.status_code == 400
    assert response.json()["code"] == "last_event_id_invalid"
