from __future__ import annotations

import json
from collections.abc import AsyncIterator
from typing import Any
from uuid import UUID

import pytest
from conftest import MemoryAgentVersionPersistence, MemoryAuthStore
from fastapi import Request
from httpx import ASGITransport, AsyncClient
from universal_agent_kernel.contracts.generated import (
    PublicAgentView,
    PublicRunCreateRequest,
    PublicRunView,
)
from universal_agent_studio_api.main import create_app
from universal_agent_studio_api.settings import Settings


def public_agent() -> PublicAgentView:
    return PublicAgentView.model_validate(
        {
            "schema_version": "0.1.0",
            "agent_id": "calculator-agent",
            "agent_version_id": "calculator-agent-v1",
            "agent_version_digest": "a" * 64,
            "localized_metadata": {
                "name": {
                    "ru-RU": "Агент-калькулятор",
                    "en-US": "Calculator Agent",
                },
                "description": {
                    "ru-RU": "Считает безопасно.",
                    "en-US": "Calculates safely.",
                },
            },
            "interface": {
                "mode": "form",
                "locales": ["ru-RU", "en-US"],
                "default_locale": "ru-RU",
                "input_fields": [
                    {
                        "id": "question",
                        "label": {
                            "ru-RU": "Задача",
                            "en-US": "Problem",
                        },
                        "schema": {"type": "string", "minLength": 1},
                        "required": True,
                    }
                ],
                "result_schema": {
                    "type": "object",
                    "properties": {"value": {"type": "number"}},
                },
            },
        }
    )


class FakePublicService:
    def __init__(self) -> None:
        self.agent = public_agent()

    async def get_agent(self, agent_id: str) -> PublicAgentView:
        assert agent_id == "calculator-agent"
        return self.agent

    async def create_run(
        self,
        agent_id: str,
        body: PublicRunCreateRequest,
        *,
        idempotency_key: str | None,
        authorization: str | None,
    ) -> PublicRunView:
        del body, idempotency_key, authorization
        return self._run(agent_id, status="queued")

    async def invoke(
        self,
        agent_id: str,
        body: PublicRunCreateRequest,
        *,
        idempotency_key: str | None,
        authorization: str | None,
    ) -> PublicRunView:
        del body, idempotency_key, authorization
        return self._run(agent_id, status="completed")

    async def get_run(
        self,
        agent_id: str,
        run_id: UUID,
        *,
        authorization: str | None,
    ) -> PublicRunView:
        del run_id, authorization
        return self._run(agent_id, status="completed")

    async def stream_events(
        self,
        request: Request,
        agent_id: str,
        run_id: UUID,
        *,
        authorization: str | None,
        after_sequence: int,
    ) -> AsyncIterator[bytes]:
        del request, agent_id, run_id, authorization, after_sequence
        yield b"id: 2\nevent: run.completed\ndata: {\"sequence\":2}\n\n"

    @staticmethod
    def _run(agent_id: str, *, status: str) -> PublicRunView:
        run_id = "11111111-1111-4111-8111-111111111111"
        return PublicRunView.model_validate(
            {
                "schema_version": "0.1.0",
                "run_id": run_id,
                "agent_id": agent_id,
                "agent_version_id": f"{agent_id}-v1",
                "agent_version_digest": "a" * 64,
                "status": status,
                "locale": "en-US",
                "output": {"value": 437} if status == "completed" else None,
                "error_code": None,
                "status_url": f"/public/v1/agents/{agent_id}/runs/{run_id}",
                "events_url": (
                    f"/public/v1/agents/{agent_id}/runs/{run_id}/events"
                ),
                "run_capability": "uascap_" + "A" * 48,
            }
        )


@pytest.fixture
def public_app() -> Any:
    return create_app(
        auth_store=MemoryAuthStore(),
        agent_persistence=MemoryAgentVersionPersistence(),
        public_service=FakePublicService(),
        settings=Settings(
            allowed_hosts=["testserver"],
            allowed_origins=["http://testserver"],
            secure_cookies=False,
        ),
    )


@pytest.mark.asyncio
async def test_public_metadata_exposes_interface_without_agent_internals(
    public_app: Any,
) -> None:
    async with AsyncClient(
        transport=ASGITransport(app=public_app),
        base_url="http://testserver",
    ) as client:
        response = await client.get(
            "/public/v1/agents/calculator-agent"
        )

    assert response.status_code == 200
    document = response.json()
    assert document["interface"]["mode"] == "form"
    serialized = json.dumps(document, sort_keys=True)
    for forbidden in (
        "prompt",
        "tools",
        "model_profiles",
        "agent_spec",
        "trace_id",
        "durable_execution_id",
    ):
        assert forbidden not in serialized
