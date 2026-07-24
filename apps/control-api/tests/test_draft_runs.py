from __future__ import annotations

import copy
from collections.abc import AsyncIterator
from pathlib import Path

import pytest
import pytest_asyncio
from conftest import MemoryAgentVersionPersistence, MemoryAuthStore
from httpx import ASGITransport, AsyncClient
from test_agent_drafts import MemoryDraftPersistence
from test_runs_api import FakeDurableExecution, MemoryRunPersistence
from universal_agent_studio_api.main import create_app
from universal_agent_studio_api.settings import Settings

ROOT = Path(__file__).parents[3]
GOLDEN_AGENT = (
    ROOT
    / "contracts"
    / "examples"
    / "v0.1.0"
    / "valid"
    / "agent.calculator.ru-en.json"
)


@pytest_asyncio.fixture
async def draft_run_harness() -> AsyncIterator[
    tuple[
        AsyncClient,
        MemoryAgentVersionPersistence,
        FakeDurableExecution,
    ]
]:
    auth = MemoryAuthStore()
    versions = MemoryAgentVersionPersistence()
    durable = FakeDurableExecution()
    app = create_app(
        auth_store=auth,
        agent_persistence=versions,
        draft_persistence=MemoryDraftPersistence(),
        run_persistence=MemoryRunPersistence(),
        durable_execution=durable,
        settings=Settings(
            allowed_hosts=["testserver"],
            allowed_origins=["http://testserver"],
            secure_cookies=False,
            max_request_bytes=1_048_576,
        ),
    )
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
        headers={"Origin": "http://testserver"},
    ) as client:
        bootstrap = await client.post(
            "/api/v1/bootstrap/owner",
            json={
                "login_name": "owner",
                "password": "correct horse battery staple",
                "preferred_locale": "en-US",
            },
        )
        csrf = bootstrap.json()["csrf_token"]
        client.headers["X-CSRF-Token"] = csrf
        imported = await client.post(
            "/api/v1/agent-versions/import",
            content=GOLDEN_AGENT.read_bytes(),
            headers={"Content-Type": "application/json"},
        )
        activated = await client.post(
            "/api/v1/agents/calculator-agent/active-version",
            json={
                "version_id": imported.json()["version_id"],
                "expected_previous_version_id": None,
            },
        )
        assert activated.status_code == 200
        yield client, versions, durable


@pytest.mark.asyncio
async def test_draft_run_uses_an_unactivated_immutable_snapshot(
    draft_run_harness: tuple[
        AsyncClient,
        MemoryAgentVersionPersistence,
        FakeDurableExecution,
    ],
) -> None:
    client, _, durable = draft_run_harness
    created = await client.post(
        "/api/v1/agents/calculator-agent/draft"
    )
    candidate = copy.deepcopy(created.json()["agent_spec"])
    candidate["localized_metadata"]["name"]["en-US"] = "Draft Math Agent"
    saved = await client.put(
        "/api/v1/agents/calculator-agent/draft",
        json={
            "expected_revision": 1,
            "agent_spec": candidate,
            "layout": created.json()["layout"],
        },
    )
    body = {
        "expected_revision": 2,
        "request_id": "22222222-2222-4222-8222-222222222222",
        "idempotency_key": "draft-run-00000001",
        "input": {"question": "What is 19 × 23?"},
        "locale": "en-US",
    }

    first = await client.post(
        "/api/v1/agents/calculator-agent/draft/runs",
        json=body,
    )
    repeated = await client.post(
        "/api/v1/agents/calculator-agent/draft/runs",
        json=body,
    )
    active = await client.get(
        "/api/v1/agents/calculator-agent/active-version"
    )

    assert saved.status_code == 200
    assert first.status_code == 201
    assert repeated.status_code == 200
    assert repeated.json()["run_id"] == first.json()["run_id"]
    assert active.json()["version_id"] == "calculator-agent-v1"
    assert len(durable.commands) == 1
    assert durable.commands[0].agent_version_id == "calculator-agent-v2"
    assert durable.commands[0].agent_version_digest == saved.json()["digest"]


@pytest.mark.asyncio
async def test_draft_run_rejects_a_stale_revision(
    draft_run_harness: tuple[
        AsyncClient,
        MemoryAgentVersionPersistence,
        FakeDurableExecution,
    ],
) -> None:
    client, _, durable = draft_run_harness
    await client.post("/api/v1/agents/calculator-agent/draft")

    response = await client.post(
        "/api/v1/agents/calculator-agent/draft/runs",
        json={
            "expected_revision": 99,
            "request_id": "33333333-3333-4333-8333-333333333333",
            "idempotency_key": "draft-run-00000002",
            "input": {"question": "What is 19 × 23?"},
            "locale": "en-US",
        },
    )

    assert response.status_code == 409
    assert response.json()["code"] == "agent_draft_revision_conflict"
    assert durable.commands == []


@pytest.mark.asyncio
async def test_draft_run_route_is_rate_limited() -> None:
    app = create_app(
        auth_store=MemoryAuthStore(),
        agent_persistence=MemoryAgentVersionPersistence(),
        draft_persistence=MemoryDraftPersistence(),
        settings=Settings(
            allowed_hosts=["testserver"],
            allowed_origins=["http://testserver"],
            secure_cookies=False,
            auth_rate_limit=2,
            auth_rate_window_seconds=60,
        ),
    )
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
        headers={"Origin": "http://testserver"},
    ) as client:
        bootstrap = await client.post(
            "/api/v1/bootstrap/owner",
            json={
                "login_name": "owner",
                "password": "correct horse battery staple",
                "preferred_locale": "en-US",
            },
        )
        client.headers["X-CSRF-Token"] = bootstrap.json()["csrf_token"]
        statuses = [
            (
                await client.post(
                    "/api/v1/agents/calculator-agent/draft/runs",
                    json={},
                )
            ).status_code
            for _ in range(3)
        ]

    assert statuses == [422, 422, 429]
