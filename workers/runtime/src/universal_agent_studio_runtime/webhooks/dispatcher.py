"""Bounded allowlisted webhook outbox dispatcher."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Protocol
from urllib.parse import urlsplit
from uuid import UUID

import httpx
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from universal_agent_kernel.contracts.canonical import canonicalize
from universal_agent_platform_store.models import (
    WebhookDelivery,
    WebhookSubscription,
)
from universal_agent_platform_store.webhook_crypto import derive_webhook_secret

from universal_agent_studio_runtime.webhooks.signing import sign_webhook

TRANSIENT_STATUS_CODES = {408, 409, 425, 429}


@dataclass(frozen=True)
class ClaimedWebhookDelivery:
    id: UUID
    target_url: str
    signing_key_id: UUID
    payload: dict[str, object]
    attempt_count: int


class WebhookDeliveryStore(Protocol):
    async def claim_due(
        self,
        *,
        now: datetime,
        limit: int,
    ) -> tuple[ClaimedWebhookDelivery, ...]: ...

    async def finish(
        self,
        delivery_id: UUID,
        *,
        attempt_count: int,
        state: str,
        next_attempt_at: datetime | None,
        status_code: int | None,
        error: str | None,
    ) -> None: ...


class WebhookHttpClient(Protocol):
    async def send(
        self,
        *,
        url: str,
        body: bytes,
        headers: dict[str, str],
        timeout_seconds: float,
        max_response_bytes: int,
    ) -> int: ...


class HttpxWebhookClient:
    def __init__(self) -> None:
        self.client = httpx.AsyncClient(follow_redirects=False)

    async def send(
        self,
        *,
        url: str,
        body: bytes,
        headers: dict[str, str],
        timeout_seconds: float,
        max_response_bytes: int,
    ) -> int:
        async with self.client.stream(
            "POST",
            url,
            content=body,
            headers=headers,
            follow_redirects=False,
            timeout=timeout_seconds,
        ) as response:
            total = 0
            async for chunk in response.aiter_bytes():
                total += len(chunk)
                if total > max_response_bytes:
                    break
            return response.status_code

    async def close(self) -> None:
        await self.client.aclose()


class SqlWebhookDeliveryStore:
    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        *,
        lease_seconds: int = 30,
    ) -> None:
        self.session_factory = session_factory
        self.lease_seconds = lease_seconds

    async def claim_due(
        self,
        *,
        now: datetime,
        limit: int,
    ) -> tuple[ClaimedWebhookDelivery, ...]:
        async with self.session_factory() as session:
            records = tuple(
                await session.scalars(
                    select(WebhookDelivery)
                    .where(
                        or_(
                            WebhookDelivery.state == "pending",
                            WebhookDelivery.state == "delivering",
                        ),
                        WebhookDelivery.next_attempt_at <= now,
                    )
                    .order_by(
                        WebhookDelivery.next_attempt_at,
                        WebhookDelivery.id,
                    )
                    .limit(limit)
                    .with_for_update(skip_locked=True)
                )
            )
            claimed: list[ClaimedWebhookDelivery] = []
            for record in records:
                subscription = await session.get(
                    WebhookSubscription,
                    record.subscription_id,
                )
                if (
                    subscription is None
                    or subscription.revoked_at is not None
                ):
                    record.state = "cancelled"
                    record.last_error = "subscription_revoked"
                    continue
                record.state = "delivering"
                record.attempt_count += 1
                record.next_attempt_at = now + timedelta(
                    seconds=self.lease_seconds
                )
                claimed.append(
                    ClaimedWebhookDelivery(
                        id=record.id,
                        target_url=subscription.target_url,
                        signing_key_id=subscription.signing_key_id,
                        payload=record.payload,
                        attempt_count=record.attempt_count,
                    )
                )
            await session.commit()
            return tuple(claimed)

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
        async with self.session_factory() as session:
            delivery = await session.scalar(
                select(WebhookDelivery)
                .where(
                    WebhookDelivery.id == delivery_id,
                    WebhookDelivery.state == "delivering",
                    WebhookDelivery.attempt_count == attempt_count,
                )
                .with_for_update()
            )
            if delivery is None:
                return
            delivery.state = state
            delivery.last_status_code = status_code
            delivery.last_error = error[:255] if error is not None else None
            if next_attempt_at is not None:
                delivery.next_attempt_at = next_attempt_at
            if state == "delivered":
                delivery.delivered_at = datetime.now(UTC)
            await session.commit()


def _origin(url: str) -> str | None:
    parsed = urlsplit(url)
    if (
        parsed.scheme not in {"http", "https"}
        or parsed.hostname is None
        or parsed.username is not None
        or parsed.password is not None
        or bool(parsed.fragment)
    ):
        return None
    host = parsed.hostname
    if ":" in host and not host.startswith("["):
        host = f"[{host}]"
    origin = f"{parsed.scheme}://{host}"
    if parsed.port is not None:
        origin += f":{parsed.port}"
    return origin


class WebhookDispatcher:
    def __init__(
        self,
        *,
        store: WebhookDeliveryStore,
        http_client: WebhookHttpClient,
        webhook_master: bytes,
        allowed_origins: list[str],
        timeout_seconds: float,
        max_response_bytes: int,
        max_attempts: int,
        batch_size: int = 20,
        poll_interval_seconds: float = 1,
    ) -> None:
        if len(webhook_master.strip()) < 32:
            raise ValueError("webhook_signing_key_too_short")
        self.store = store
        self.http_client = http_client
        self.webhook_master = webhook_master.strip()
        self.allowed_origins = {
            origin.rstrip("/") for origin in allowed_origins
        }
        self.timeout_seconds = timeout_seconds
        self.max_response_bytes = max_response_bytes
        self.max_attempts = max_attempts
        self.batch_size = batch_size
        self.poll_interval_seconds = poll_interval_seconds

    async def dispatch_once(self, *, now: datetime | None = None) -> int:
        current = now or datetime.now(UTC)
        deliveries = await self.store.claim_due(
            now=current,
            limit=self.batch_size,
        )
        for delivery in deliveries:
            await self._deliver(delivery, current)
        return len(deliveries)

    async def _deliver(
        self,
        delivery: ClaimedWebhookDelivery,
        now: datetime,
    ) -> None:
        if _origin(delivery.target_url) not in self.allowed_origins:
            await self.store.finish(
                delivery.id,
                attempt_count=delivery.attempt_count,
                state="failed",
                next_attempt_at=None,
                status_code=None,
                error="webhook_origin_not_allowed",
            )
            return
        timestamp = int(now.timestamp())
        body = canonicalize(delivery.payload)
        secret = derive_webhook_secret(
            self.webhook_master,
            delivery.signing_key_id,
        ).encode("ascii")
        headers = {
            "Content-Type": "application/json",
            "User-Agent": "Universal-Agent-Studio-Webhook/1",
            "X-UAS-Delivery": str(delivery.id),
            "X-UAS-Timestamp": str(timestamp),
            "X-UAS-Signature": sign_webhook(secret, timestamp, body),
        }
        try:
            status_code = await self.http_client.send(
                url=delivery.target_url,
                body=body,
                headers=headers,
                timeout_seconds=self.timeout_seconds,
                max_response_bytes=self.max_response_bytes,
            )
        except (httpx.HTTPError, TimeoutError, OSError):
            await self._finish_transient(
                delivery,
                now,
                status_code=None,
                error="transport_failure",
            )
            return
        if 200 <= status_code < 300:
            await self.store.finish(
                delivery.id,
                attempt_count=delivery.attempt_count,
                state="delivered",
                next_attempt_at=None,
                status_code=status_code,
                error=None,
            )
        elif (
            status_code in TRANSIENT_STATUS_CODES
            or 500 <= status_code < 600
        ):
            await self._finish_transient(
                delivery,
                now,
                status_code=status_code,
                error="http_transient_failure",
            )
        else:
            await self.store.finish(
                delivery.id,
                attempt_count=delivery.attempt_count,
                state="failed",
                next_attempt_at=None,
                status_code=status_code,
                error="http_permanent_failure",
            )

    async def _finish_transient(
        self,
        delivery: ClaimedWebhookDelivery,
        now: datetime,
        *,
        status_code: int | None,
        error: str,
    ) -> None:
        if delivery.attempt_count >= self.max_attempts:
            state = "failed"
            next_attempt_at = None
        else:
            state = "pending"
            delay = 2 ** min(delivery.attempt_count, 6)
            next_attempt_at = now + timedelta(seconds=delay)
        await self.store.finish(
            delivery.id,
            attempt_count=delivery.attempt_count,
            state=state,
            next_attempt_at=next_attempt_at,
            status_code=status_code,
            error=error,
        )

    async def run(self, stop: asyncio.Event) -> None:
        while not stop.is_set():
            await self.dispatch_once()
            try:
                await asyncio.wait_for(
                    stop.wait(),
                    timeout=self.poll_interval_seconds,
                )
            except TimeoutError:
                continue
