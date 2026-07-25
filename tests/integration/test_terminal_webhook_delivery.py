from __future__ import annotations

import asyncio
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, cast
from uuid import UUID, uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker
from universal_agent_kernel.contracts.canonical import content_digest
from universal_agent_platform_store.models import (
    AgentVersion,
    Run,
    WebhookDelivery,
)
from universal_agent_platform_store.repositories.agents import AgentRepository
from universal_agent_platform_store.repositories.webhooks import WebhookRepository
from universal_agent_platform_store.scope import RequestScope
from universal_agent_studio_api.runs.service import (
    RunCreateData,
    SqlRunPersistence,
)
from universal_agent_studio_runtime.webhooks.dispatcher import (
    ClaimedWebhookDelivery,
    HttpxWebhookClient,
    SqlWebhookDeliveryStore,
    WebhookDispatcher,
)

ROOT = Path(__file__).parents[2]
GOLDEN = (
    ROOT
    / "contracts"
    / "examples"
    / "v0.1.0"
    / "valid"
    / "agent.calculator.ru-en.json"
)


class SingleDeliveryStore:
    def __init__(self, delivery: ClaimedWebhookDelivery) -> None:
        self.delivery = delivery
        self.finished: dict[str, object] | None = None

    async def claim_due(
        self,
        *,
        now: datetime,
        limit: int,
    ) -> tuple[ClaimedWebhookDelivery, ...]:
        del now, limit
        return (self.delivery,)

    async def finish(
        self,
        delivery_id: UUID,
        *,
        attempt_count: int,
        state: str,
        next_attempt_at: datetime | None,
        status_code: int | None,
        error: str | None,
    ) -> None:
        self.finished = {
            "delivery_id": delivery_id,
            "attempt_count": attempt_count,
            "state": state,
            "next_attempt_at": next_attempt_at,
            "status_code": status_code,
            "error": error,
        }


async def _seed_agent(
    database_session: AsyncSession,
    request_scope: RequestScope,
) -> tuple[dict[str, Any], AgentVersion]:
    spec = cast(dict[str, Any], json.loads(GOLDEN.read_text(encoding="utf-8")))
    version, _ = await AgentRepository(
        database_session,
        request_scope,
    ).import_version(spec, content_digest(spec))
    await database_session.commit()
    return spec, version


@pytest.mark.asyncio
async def test_dispatcher_performs_signed_http_delivery() -> None:
    received: asyncio.Future[tuple[dict[str, str], bytes]] = (
        asyncio.get_running_loop().create_future()
    )

    async def receive(
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter,
    ) -> None:
        raw_headers = await reader.readuntil(b"\r\n\r\n")
        lines = raw_headers.decode("ascii").split("\r\n")
        headers = {
            key.lower(): value.strip()
            for line in lines[1:]
            if line and (key_value := line.split(":", 1))
            for key, value in [key_value]
        }
        body = await reader.readexactly(int(headers["content-length"]))
        received.set_result((headers, body))
        writer.write(b"HTTP/1.1 204 No Content\r\nConnection: close\r\n\r\n")
        await writer.drain()
        writer.close()
        await writer.wait_closed()

    server = await asyncio.start_server(receive, "127.0.0.1", 0)
    port = server.sockets[0].getsockname()[1]
    delivery = ClaimedWebhookDelivery(
        id=uuid4(),
        target_url=f"http://127.0.0.1:{port}/terminal",
        signing_key_id=uuid4(),
        payload={"schema_version": "0.1.0", "status": "completed"},
        attempt_count=1,
    )
    store = SingleDeliveryStore(delivery)
    client = HttpxWebhookClient()
    dispatcher = WebhookDispatcher(
        store=store,
        http_client=client,
        webhook_master=b"w" * 32,
        allowed_origins=[f"http://127.0.0.1:{port}"],
        timeout_seconds=2,
        max_response_bytes=1024,
        max_attempts=4,
    )
    try:
        assert await dispatcher.dispatch_once() == 1
        headers, body = await asyncio.wait_for(received, timeout=2)
    finally:
        await client.close()
        server.close()
        await server.wait_closed()

    assert json.loads(body) == delivery.payload
    assert headers["x-uas-delivery"] == str(delivery.id)
    assert headers["x-uas-signature"].startswith("v1=")
    assert store.finished is not None
    assert store.finished["state"] == "delivered"
    assert store.finished["attempt_count"] == 1


@pytest.mark.asyncio
async def test_failed_durable_start_enqueues_terminal_webhook_atomically(
    database_engine: AsyncEngine,
    database_session: AsyncSession,
    request_scope: RequestScope,
) -> None:
    _, version = await _seed_agent(database_session, request_scope)
    await WebhookRepository(database_session, request_scope).create(
        "calculator-agent",
        label="Failed starts",
        target_url="http://example.test:9090/terminal",
        events=["run.failed"],
        signing_key_id=uuid4(),
    )
    await database_session.commit()
    persistence = SqlRunPersistence(
        async_sessionmaker(database_engine, expire_on_commit=False)
    )
    stored, _ = await persistence.create_idempotent(
        scope=request_scope,
        data=RunCreateData(
            request_id=uuid4(),
            agent_version_internal_id=version.id,
            agent_version_id="calculator-agent-v1",
            agent_version_digest=version.digest,
            idempotency_key="failed-start-test",
            input={"expression": "19 * 23"},
            locale="en-US",
        ),
        request_digest="d" * 64,
    )

    await persistence.finalize_start_failure(
        scope=request_scope,
        run=stored,
        error_code="durable_execution_unavailable",
    )

    async with AsyncSession(database_engine) as verification:
        delivery = await verification.scalar(select(WebhookDelivery))
    assert delivery is not None
    assert delivery.event_type == "run.failed"
    assert delivery.payload["run_id"] == str(stored.id)
    assert delivery.payload["error_code"] == "invocation_unavailable"


@pytest.mark.asyncio
async def test_stale_webhook_lease_cannot_finish_a_newer_attempt(
    database_engine: AsyncEngine,
    database_session: AsyncSession,
    request_scope: RequestScope,
) -> None:
    _, version = await _seed_agent(database_session, request_scope)
    repository = WebhookRepository(database_session, request_scope)
    subscription = await repository.create(
        "calculator-agent",
        label="Leases",
        target_url="http://example.test:9090/terminal",
        events=["run.completed"],
        signing_key_id=uuid4(),
    )
    run = Run(
        id=uuid4(),
        workspace_id=request_scope.workspace_id,
        project_id=request_scope.project_id,
        agent_version_id=version.id,
        status="completed",
        locale="en-US",
        input_document={"expression": "19 * 23"},
        output_document={"value": 437},
        cancel_requested=False,
    )
    database_session.add(run)
    await database_session.flush()
    delivery, _ = await repository.enqueue(
        subscription=subscription,
        run_id=run.id,
        event_sequence=3,
        event_type="run.completed",
        payload={"status": "completed"},
    )
    await database_session.commit()
    store = SqlWebhookDeliveryStore(
        async_sessionmaker(database_engine, expire_on_commit=False),
        lease_seconds=1,
    )
    first_now = datetime.now(UTC) + timedelta(seconds=1)
    first = (await store.claim_due(now=first_now, limit=1))[0]
    second = (
        await store.claim_due(
            now=first_now + timedelta(seconds=2),
            limit=1,
        )
    )[0]

    await store.finish(
        delivery.id,
        attempt_count=first.attempt_count,
        state="delivered",
        next_attempt_at=None,
        status_code=204,
        error=None,
    )

    async with AsyncSession(database_engine) as verification:
        current = await verification.get(WebhookDelivery, delivery.id)
        assert current is not None
        assert current.state == "delivering"
        assert current.attempt_count == second.attempt_count == 2

    await store.finish(
        delivery.id,
        attempt_count=second.attempt_count,
        state="delivered",
        next_attempt_at=None,
        status_code=204,
        error=None,
    )
    async with AsyncSession(database_engine) as verification:
        current = await verification.get(WebhookDelivery, delivery.id)
        assert current is not None
        assert current.state == "delivered"
