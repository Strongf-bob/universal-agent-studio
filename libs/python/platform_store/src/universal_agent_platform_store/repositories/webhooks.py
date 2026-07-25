"""Scoped webhook subscriptions and durable delivery outbox."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from universal_agent_platform_store.models import (
    Agent,
    AgentVersion,
    Run,
    WebhookDelivery,
    WebhookSubscription,
    utc_now,
)
from universal_agent_platform_store.repositories.base import ScopedRepository
from universal_agent_platform_store.scope import RequestScope


class WebhookNotFound(RuntimeError):
    pass


class WebhookRepository(ScopedRepository):
    def __init__(
        self,
        session: AsyncSession,
        scope: RequestScope | None,
    ) -> None:
        super().__init__(session, scope)
        self.workspace_id, self.project_id = self.scope.tenant_ids()

    async def _agent(self, agent_key: str) -> Agent:
        agent = await self.session.scalar(
            select(Agent).where(
                Agent.workspace_id == self.workspace_id,
                Agent.project_id == self.project_id,
                Agent.agent_key == agent_key,
            )
        )
        if agent is None:
            raise WebhookNotFound("agent_not_found")
        return agent

    async def create(
        self,
        agent_key: str,
        *,
        label: str,
        target_url: str,
        events: list[str],
        signing_key_id: UUID,
    ) -> WebhookSubscription:
        agent = await self._agent(agent_key)
        record = WebhookSubscription(
            id=uuid4(),
            workspace_id=self.workspace_id,
            project_id=self.project_id,
            agent_id=agent.id,
            label=label,
            target_url=target_url,
            events=events,
            signing_key_id=signing_key_id,
        )
        self.session.add(record)
        await self.session.flush()
        return record

    async def list(self, agent_key: str) -> tuple[WebhookSubscription, ...]:
        agent = await self._agent(agent_key)
        return tuple(
            await self.session.scalars(
                select(WebhookSubscription)
                .where(
                    WebhookSubscription.workspace_id == self.workspace_id,
                    WebhookSubscription.project_id == self.project_id,
                    WebhookSubscription.agent_id == agent.id,
                )
                .order_by(WebhookSubscription.created_at.desc())
            )
        )

    async def revoke(
        self,
        agent_key: str,
        subscription_id: UUID,
    ) -> WebhookSubscription | None:
        agent = await self._agent(agent_key)
        record = await self.session.scalar(
            select(WebhookSubscription)
            .where(
                WebhookSubscription.id == subscription_id,
                WebhookSubscription.workspace_id == self.workspace_id,
                WebhookSubscription.project_id == self.project_id,
                WebhookSubscription.agent_id == agent.id,
            )
            .with_for_update()
        )
        if record is not None and record.revoked_at is None:
            record.revoked_at = utc_now()
            await self.session.flush()
        return record

    async def enqueue(
        self,
        *,
        subscription: WebhookSubscription,
        run_id: UUID,
        event_sequence: int,
        event_type: str,
        payload: dict[str, object],
    ) -> tuple[WebhookDelivery, bool]:
        existing = await self.session.scalar(
            select(WebhookDelivery).where(
                WebhookDelivery.subscription_id == subscription.id,
                WebhookDelivery.run_id == run_id,
                WebhookDelivery.event_sequence == event_sequence,
            )
        )
        if existing is not None:
            return existing, False
        delivery_id = uuid4()
        delivery = WebhookDelivery(
            id=delivery_id,
            workspace_id=subscription.workspace_id,
            project_id=subscription.project_id,
            subscription_id=subscription.id,
            run_id=run_id,
            event_sequence=event_sequence,
            event_type=event_type,
            payload={**payload, "delivery_id": str(delivery_id)},
        )
        self.session.add(delivery)
        await self.session.flush()
        return delivery, True

    async def enqueue_terminal(
        self,
        *,
        run_id: UUID,
        trace: dict[str, object],
    ) -> tuple[WebhookDelivery, ...]:
        row = (
            await self.session.execute(
                select(Run, AgentVersion, Agent)
                .join(
                    AgentVersion,
                    AgentVersion.id == Run.agent_version_id,
                )
                .join(Agent, Agent.id == AgentVersion.agent_id)
                .where(
                    Run.id == run_id,
                    Run.workspace_id == self.workspace_id,
                    Run.project_id == self.project_id,
                )
            )
        ).one_or_none()
        if row is None:
            raise WebhookNotFound("run_not_found")
        run, version, agent = row
        raw_events = trace.get("events")
        if not isinstance(raw_events, list):
            raise ValueError("terminal_trace_events_missing")
        terminal = next(
            (
                event
                for event in reversed(raw_events)
                if isinstance(event, dict)
                and event.get("type")
                in {"run.completed", "run.failed", "run.cancelled"}
            ),
            None,
        )
        if terminal is None:
            raise ValueError("terminal_trace_event_missing")
        event_type = str(terminal["type"])
        sequence = int(terminal["sequence"])
        status = str(trace.get("status"))
        output = trace.get("output")
        if event_type == "run.failed":
            error_code: str | None = "invocation_unavailable"
        elif event_type == "run.cancelled":
            error_code = "run_cancelled"
        else:
            error_code = None
        subscriptions = tuple(
            await self.session.scalars(
                select(WebhookSubscription).where(
                    WebhookSubscription.workspace_id == self.workspace_id,
                    WebhookSubscription.project_id == self.project_id,
                    WebhookSubscription.agent_id == agent.id,
                    WebhookSubscription.revoked_at.is_(None),
                )
            )
        )
        created: list[WebhookDelivery] = []
        for subscription in subscriptions:
            if event_type not in subscription.events:
                continue
            delivery, _ = await self.enqueue(
                subscription=subscription,
                run_id=run.id,
                event_sequence=sequence,
                event_type=event_type,
                payload={
                    "schema_version": "0.1.0",
                    "agent_id": agent.agent_key,
                    "agent_version_id": (
                        f"{agent.agent_key}-v{version.version_number}"
                    ),
                    "agent_version_digest": version.digest,
                    "run_id": str(run.id),
                    "event_type": event_type,
                    "status": status,
                    "result": (
                        output
                        if event_type == "run.completed"
                        and isinstance(output, dict)
                        else None
                    ),
                    "error_code": error_code,
                    "occurred_at": terminal.get("occurred_at"),
                },
            )
            created.append(delivery)
        return tuple(created)

    async def claim_due(
        self,
        *,
        now: datetime,
        limit: int,
    ) -> tuple[WebhookDelivery, ...]:
        deliveries = tuple(
            await self.session.scalars(
                select(WebhookDelivery)
                .where(
                    WebhookDelivery.state == "pending",
                    WebhookDelivery.next_attempt_at <= now,
                )
                .order_by(WebhookDelivery.next_attempt_at, WebhookDelivery.id)
                .limit(limit)
                .with_for_update(skip_locked=True)
            )
        )
        for delivery in deliveries:
            delivery.state = "delivering"
            delivery.attempt_count += 1
        await self.session.flush()
        return deliveries

    async def finish_attempt(
        self,
        delivery_id: UUID,
        *,
        state: str,
        next_attempt_at: datetime | None = None,
        status_code: int | None = None,
        error: str | None = None,
    ) -> WebhookDelivery | None:
        delivery = await self.session.scalar(
            select(WebhookDelivery)
            .where(WebhookDelivery.id == delivery_id)
            .with_for_update()
        )
        if delivery is None:
            return None
        delivery.state = state
        delivery.last_status_code = status_code
        delivery.last_error = error[:255] if error is not None else None
        if next_attempt_at is not None:
            delivery.next_attempt_at = next_attempt_at
        if state == "delivered":
            delivery.delivered_at = utc_now()
        await self.session.flush()
        return delivery
