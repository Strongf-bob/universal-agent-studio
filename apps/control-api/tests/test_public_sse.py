from __future__ import annotations

from typing import Any

import pytest
from httpx import ASGITransport, AsyncClient
from test_public_agents import public_app

__all__ = ["public_app"]


@pytest.mark.asyncio
async def test_public_sse_passes_bounded_resume_cursor(
    public_app: Any,
) -> None:
    async with AsyncClient(
        transport=ASGITransport(app=public_app),
        base_url="http://testserver",
    ) as client:
        response = await client.get(
            "/public/v1/agents/calculator-agent/runs/"
            "11111111-1111-4111-8111-111111111111/events",
            headers={
                "Authorization": "Bearer uascap_" + "A" * 48,
                "Last-Event-ID": "1",
            },
        )

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    assert "id: 1\n" not in response.text
    assert "id: 2\nevent: run.completed\n" in response.text


@pytest.mark.asyncio
async def test_public_sse_rejects_invalid_resume_cursor(
    public_app: Any,
) -> None:
    async with AsyncClient(
        transport=ASGITransport(app=public_app),
        base_url="http://testserver",
    ) as client:
        response = await client.get(
            "/public/v1/agents/calculator-agent/runs/"
            "11111111-1111-4111-8111-111111111111/events",
            headers={"Last-Event-ID": "-1"},
        )

    assert response.status_code == 400
    assert response.json()["code"] == "last_event_id_invalid"
