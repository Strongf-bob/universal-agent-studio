from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

import pytest
from universal_agent_studio_runtime.webhooks.dispatcher import (
    ClaimedWebhookDelivery,
    WebhookDispatcher,
)


class FakeStore:
    def __init__(self, delivery: ClaimedWebhookDelivery) -> None:
        self.delivery = delivery
        self.finished: list[dict[str, object]] = []

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
        self.finished.append(
            {
                "delivery_id": delivery_id,
                "attempt_count": attempt_count,
                "state": state,
                "next_attempt_at": next_attempt_at,
                "status_code": status_code,
                "error": error,
            }
        )


class FakeHttpClient:
    def __init__(self, status_code: int) -> None:
        self.status_code = status_code
        self.requests: list[dict[str, object]] = []

    async def send(
        self,
        *,
        url: str,
        body: bytes,
        headers: dict[str, str],
        timeout_seconds: float,
        max_response_bytes: int,
    ) -> int:
        self.requests.append(
            {
                "url": url,
                "body": body,
                "headers": headers,
                "timeout_seconds": timeout_seconds,
                "max_response_bytes": max_response_bytes,
            }
        )
        return self.status_code


def delivery() -> ClaimedWebhookDelivery:
    return ClaimedWebhookDelivery(
        id=UUID("00000000-0000-4000-8000-000000000001"),
        target_url="http://example.test:9090/hooks/terminal",
        signing_key_id=UUID("00000000-0000-4000-8000-000000000002"),
        payload={
            "delivery_id": "00000000-0000-4000-8000-000000000001",
            "status": "completed",
        },
        attempt_count=1,
    )


@pytest.mark.asyncio
async def test_dispatcher_signs_and_completes_successful_delivery() -> None:
    claimed = delivery()
    store = FakeStore(claimed)
    client = FakeHttpClient(204)
    dispatcher = WebhookDispatcher(
        store=store,
        http_client=client,
        webhook_master=b"w" * 32,
        allowed_origins=["http://example.test:9090"],
        timeout_seconds=2,
        max_response_bytes=1024,
        max_attempts=4,
    )

    count = await dispatcher.dispatch_once(
        now=datetime(2026, 7, 25, 12, 0, tzinfo=UTC)
    )

    assert count == 1
    assert store.finished[0]["state"] == "delivered"
    assert store.finished[0]["attempt_count"] == claimed.attempt_count
    headers = client.requests[0]["headers"]
    assert isinstance(headers, dict)
    assert headers["X-UAS-Delivery"] == str(claimed.id)
    assert headers["X-UAS-Timestamp"] == "1784980800"
    assert str(headers["X-UAS-Signature"]).startswith("v1=")


@pytest.mark.asyncio
async def test_redirect_is_a_permanent_failure_without_following() -> None:
    store = FakeStore(delivery())
    client = FakeHttpClient(302)
    dispatcher = WebhookDispatcher(
        store=store,
        http_client=client,
        webhook_master=b"w" * 32,
        allowed_origins=["http://example.test:9090"],
        timeout_seconds=2,
        max_response_bytes=1024,
        max_attempts=4,
    )

    await dispatcher.dispatch_once(
        now=datetime(2026, 7, 25, 12, 0, tzinfo=UTC)
    )

    assert len(client.requests) == 1
    assert store.finished[0]["state"] == "failed"
    assert store.finished[0]["error"] == "http_permanent_failure"


@pytest.mark.asyncio
async def test_transient_failure_is_retried_with_stable_delivery_id() -> None:
    claimed = delivery()
    store = FakeStore(claimed)
    dispatcher = WebhookDispatcher(
        store=store,
        http_client=FakeHttpClient(503),
        webhook_master=b"w" * 32,
        allowed_origins=["http://example.test:9090"],
        timeout_seconds=2,
        max_response_bytes=1024,
        max_attempts=4,
    )
    now = datetime(2026, 7, 25, 12, 0, tzinfo=UTC)

    await dispatcher.dispatch_once(now=now)

    result = store.finished[0]
    assert result["delivery_id"] == claimed.id
    assert result["state"] == "pending"
    assert isinstance(result["next_attempt_at"], datetime)
    assert result["next_attempt_at"] > now
