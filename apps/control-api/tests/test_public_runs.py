from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

import pytest
from httpx import ASGITransport, AsyncClient
from test_public_agents import public_app
from universal_agent_studio_api.publishing.principals import (
    issue_run_capability,
    verify_run_capability,
)

__all__ = ["public_app"]


def test_run_capability_is_bound_to_exact_run_agent_project_and_expiry() -> None:
    expires_at = datetime.now(UTC) + timedelta(minutes=5)
    capability = issue_run_capability(
        b"c" * 32,
        workspace_id=UUID("aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"),
        project_id=UUID("bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb"),
        agent_id="calculator-agent",
        run_id=UUID("11111111-1111-4111-8111-111111111111"),
        expires_at=expires_at,
    )

    principal = verify_run_capability(
        b"c" * 32,
        capability,
        agent_id="calculator-agent",
        run_id=UUID("11111111-1111-4111-8111-111111111111"),
        now=datetime.now(UTC),
    )

    assert principal.agent_id == "calculator-agent"
    assert principal.run_id == UUID("11111111-1111-4111-8111-111111111111")
    with pytest.raises(ValueError, match="run_capability_invalid"):
        verify_run_capability(
            b"c" * 32,
            capability,
            agent_id="other-agent",
            run_id=principal.run_id,
            now=datetime.now(UTC),
        )


@pytest.mark.asyncio
async def test_public_async_and_sync_run_statuses(public_app: Any) -> None:
    async with AsyncClient(
        transport=ASGITransport(app=public_app),
        base_url="http://testserver",
        headers={"Origin": "http://testserver"},
    ) as client:
        async_response = await client.post(
            "/public/v1/agents/calculator-agent/runs",
            json={"input": {"question": "19 * 23"}, "locale": "en-US"},
        )
        sync_response = await client.post(
            "/public/v1/agents/calculator-agent/invoke",
            json={"input": {"question": "19 * 23"}, "locale": "en-US"},
        )

    assert async_response.status_code == 202
    assert async_response.json()["status"] == "queued"
    assert async_response.json()["run_capability"].startswith("uascap_")
    assert sync_response.status_code == 200
    assert sync_response.json()["output"] == {"value": 437}
