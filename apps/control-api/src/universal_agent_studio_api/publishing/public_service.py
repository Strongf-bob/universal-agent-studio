"""Sanitized public metadata, invocation and resumable event delivery."""

from __future__ import annotations

import asyncio
import hashlib
import time
from collections.abc import AsyncIterator
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any, Protocol, cast
from uuid import UUID, uuid4, uuid5

from fastapi import Request
from sqlalchemy import exists, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from universal_agent_kernel.contracts.canonical import canonicalize
from universal_agent_kernel.contracts.generated import (
    PublicAgentView,
    PublicRunCreateRequest,
    PublicRunEvent,
    PublicRunView,
)
from universal_agent_platform_store.models import (
    Agent,
    AgentActiveVersion,
    AgentApiKey,
    AgentPublicationEvent,
    AgentVersion,
    utc_now,
)
from universal_agent_platform_store.scope import RequestScope

from universal_agent_studio_api.agents.models import StoredAgentVersion
from universal_agent_studio_api.errors import ApiError
from universal_agent_studio_api.publishing.crypto import verify_api_key_hash
from universal_agent_studio_api.publishing.principals import (
    PublicPrincipal,
    issue_run_capability,
    verify_run_capability,
)
from universal_agent_studio_api.runs.service import (
    TERMINAL_EVENTS,
    TERMINAL_STATUSES,
    CreateRunRequest,
    RunService,
    RunView,
)


class PublicServicePort(Protocol):
    async def get_agent(self, agent_id: str) -> PublicAgentView: ...

    async def create_run(
        self,
        agent_id: str,
        body: PublicRunCreateRequest,
        *,
        idempotency_key: str | None,
        authorization: str | None,
    ) -> PublicRunView: ...

    async def invoke(
        self,
        agent_id: str,
        body: PublicRunCreateRequest,
        *,
        idempotency_key: str | None,
        authorization: str | None,
    ) -> PublicRunView: ...

    async def get_run(
        self,
        agent_id: str,
        run_id: UUID,
        *,
        authorization: str | None,
    ) -> PublicRunView: ...

    async def authorize_events(
        self,
        agent_id: str,
        run_id: UUID,
        *,
        authorization: str | None,
    ) -> None: ...

    def stream_events(
        self,
        request: Request,
        agent_id: str,
        run_id: UUID,
        *,
        authorization: str | None,
        after_sequence: int,
    ) -> AsyncIterator[bytes]: ...


@dataclass(frozen=True)
class ResolvedPublicAgent:
    agent: Agent
    version: StoredAgentVersion
    scope: RequestScope


class PublicService:
    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        *,
        run_service: RunService,
        api_key_hash_master: bytes,
        capability_master: bytes,
        capability_ttl_seconds: int,
        sync_wait_seconds: float,
        poll_interval_seconds: float,
        heartbeat_seconds: float,
        max_polls: int,
    ) -> None:
        self.session_factory = session_factory
        self.run_service = run_service
        self.api_key_hash_master = api_key_hash_master
        self.capability_master = capability_master
        self.capability_ttl_seconds = capability_ttl_seconds
        self.sync_wait_seconds = sync_wait_seconds
        self.poll_interval_seconds = poll_interval_seconds
        self.heartbeat_seconds = heartbeat_seconds
        self.max_polls = max_polls

    async def _resolve_agent(self, agent_id: str) -> ResolvedPublicAgent:
        async with self.session_factory() as session:
            rows = list(
                (
                    await session.execute(
                        select(Agent, AgentVersion)
                        .join(
                            AgentActiveVersion,
                            AgentActiveVersion.agent_id == Agent.id,
                        )
                        .join(
                            AgentVersion,
                            AgentVersion.id
                            == AgentActiveVersion.version_id,
                        )
                        .where(
                            Agent.agent_key == agent_id,
                            exists(
                                select(AgentPublicationEvent.id).where(
                                    AgentPublicationEvent.agent_id == Agent.id,
                                    AgentPublicationEvent.workspace_id
                                    == Agent.workspace_id,
                                    AgentPublicationEvent.project_id
                                    == Agent.project_id,
                                )
                            ),
                        )
                        .limit(2)
                    )
                ).all()
            )
        if len(rows) != 1:
            raise ApiError(404, "agent_not_published")
        agent, version = rows[0]
        return ResolvedPublicAgent(
            agent=agent,
            version=StoredAgentVersion(
                id=version.id,
                agent_id=agent.agent_key,
                version_number=version.version_number,
                schema_version=version.schema_version,
                digest=version.digest,
                agent_spec=cast(dict[str, Any], version.agent_spec),
            ),
            scope=RequestScope(
                workspace_id=agent.workspace_id,
                project_id=agent.project_id,
            ),
        )

    async def get_agent(self, agent_id: str) -> PublicAgentView:
        resolved = await self._resolve_agent(agent_id)
        return PublicAgentView.model_validate(
            {
                "schema_version": "0.1.0",
                "agent_id": agent_id,
                "agent_version_id": resolved.version.public_id,
                "agent_version_digest": resolved.version.digest,
                "localized_metadata": resolved.version.agent_spec[
                    "localized_metadata"
                ],
                "interface": resolved.version.agent_spec["interface"],
            }
        )

    @staticmethod
    def _bearer(authorization: str | None) -> str | None:
        if authorization is None:
            return None
        scheme, separator, value = authorization.partition(" ")
        if (
            not separator
            or scheme.lower() != "bearer"
            or not value
            or " " in value
        ):
            raise ApiError(401, "authentication_required")
        return value

    async def _authenticate_api_key(
        self,
        raw_key: str,
        *,
        agent_id: str,
        required_scope: str,
    ) -> PublicPrincipal:
        parts = raw_key.split("_", 3)
        if (
            len(parts) != 4
            or parts[0:2] != ["uas", "live"]
            or len(parts[2]) != 16
        ):
            raise ApiError(401, "authentication_required")
        prefix = parts[2]
        async with self.session_factory() as session:
            row = (
                await session.execute(
                    select(AgentApiKey, Agent)
                    .join(Agent, Agent.id == AgentApiKey.agent_id)
                    .where(AgentApiKey.prefix == prefix)
                )
            ).one_or_none()
            if row is None:
                raise ApiError(401, "authentication_required")
            record, agent = row
            now = datetime.now(UTC)
            valid_identity = (
                agent.agent_key == agent_id
                and record.revoked_at is None
                and (
                    record.expires_at is None
                    or record.expires_at > now
                )
                and verify_api_key_hash(
                    self.api_key_hash_master,
                    raw_key,
                    record.key_hash,
                )
            )
            if not valid_identity:
                raise ApiError(401, "authentication_required")
            if required_scope not in record.scopes:
                raise ApiError(403, "insufficient_scope")
            record.last_used_at = utc_now()
            await session.commit()
            return PublicPrincipal(
                kind="api_key",
                workspace_id=record.workspace_id,
                project_id=record.project_id,
                agent_id=agent.agent_key,
                key_id=record.id,
                scopes=frozenset(record.scopes),
            )

    async def _create_principal(
        self,
        resolved: ResolvedPublicAgent,
        authorization: str | None,
    ) -> PublicPrincipal:
        raw = self._bearer(authorization)
        if raw is None:
            workspace_id, project_id = resolved.scope.tenant_ids()
            return PublicPrincipal(
                kind="published_web",
                workspace_id=workspace_id,
                project_id=project_id,
                agent_id=resolved.agent.agent_key,
                scopes=frozenset({"runs:create"}),
            )
        principal = await self._authenticate_api_key(
            raw,
            agent_id=resolved.agent.agent_key,
            required_scope="runs:create",
        )
        if (
            principal.workspace_id,
            principal.project_id,
        ) != resolved.scope.tenant_ids():
            raise ApiError(401, "authentication_required")
        return principal

    async def _read_principal(
        self,
        *,
        agent_id: str,
        run_id: UUID,
        authorization: str | None,
        required_scope: str,
    ) -> PublicPrincipal:
        raw = self._bearer(authorization)
        if raw is None:
            raise ApiError(401, "authentication_required")
        if raw.startswith("uascap_"):
            try:
                principal = verify_run_capability(
                    self.capability_master,
                    raw,
                    agent_id=agent_id,
                    run_id=run_id,
                )
            except ValueError as error:
                raise ApiError(401, "authentication_required") from error
            if required_scope not in principal.scopes:
                raise ApiError(403, "insufficient_scope")
            return principal
        return await self._authenticate_api_key(
            raw,
            agent_id=agent_id,
            required_scope=required_scope,
        )

    @staticmethod
    def _scope(principal: PublicPrincipal) -> RequestScope:
        return RequestScope(
            workspace_id=principal.workspace_id,
            project_id=principal.project_id,
        )

    @staticmethod
    def _run_belongs_to_agent(run: RunView, agent_id: str) -> bool:
        version_agent, separator, number = run.agent_version_id.rpartition("-v")
        return bool(separator and number.isdigit() and version_agent == agent_id)

    def _view(
        self,
        run: RunView,
        *,
        agent_id: str,
        capability: str | None = None,
    ) -> PublicRunView:
        error_code: str | None = None
        if run.status == "failed":
            error_code = "invocation_unavailable"
        elif run.status == "cancelled":
            error_code = "run_cancelled"
        document: dict[str, Any] = {
            "schema_version": "0.1.0",
            "run_id": str(run.run_id),
            "agent_id": agent_id,
            "agent_version_id": run.agent_version_id,
            "agent_version_digest": run.agent_version_digest,
            "status": run.status,
            "locale": run.locale,
            "output": run.output if run.status == "completed" else None,
            "error_code": error_code,
            "status_url": (
                f"/public/v1/agents/{agent_id}/runs/{run.run_id}"
            ),
            "events_url": (
                f"/public/v1/agents/{agent_id}/runs/{run.run_id}/events"
            ),
        }
        if capability is not None:
            document["run_capability"] = capability
        return PublicRunView.model_validate(document)

    async def create_run(
        self,
        agent_id: str,
        body: PublicRunCreateRequest,
        *,
        idempotency_key: str | None,
        authorization: str | None,
    ) -> PublicRunView:
        resolved = await self._resolve_agent(agent_id)
        principal = await self._create_principal(resolved, authorization)
        if principal.kind == "api_key":
            if idempotency_key is None or not 16 <= len(idempotency_key) <= 128:
                raise ApiError(422, "idempotency_key_required")
            key_material = hashlib.sha256(
                idempotency_key.encode("utf-8")
            ).hexdigest()[:32]
            assert principal.key_id is not None
            durable_key = f"api:{principal.key_id.hex[:16]}:{key_material}"
            request_id = uuid5(principal.key_id, idempotency_key)
        else:
            durable_key = f"web:{uuid4().hex}"
            request_id = uuid4()
        request = CreateRunRequest(
            schema_version="0.1.0",
            request_id=request_id,
            agent_version_id=resolved.version.public_id,
            agent_version_digest=resolved.version.digest,
            idempotency_key=durable_key,
            input=body.input,
            locale=body.locale.value,
        )
        created = await self.run_service.create_resolved_run(
            request,
            resolved.scope,
            resolved.version,
        )
        run = await self.run_service.get_run(created.run_id, resolved.scope)
        capability: str | None = None
        if principal.kind == "published_web":
            workspace_id, project_id = resolved.scope.tenant_ids()
            capability = issue_run_capability(
                self.capability_master,
                workspace_id=workspace_id,
                project_id=project_id,
                agent_id=agent_id,
                run_id=run.run_id,
                expires_at=(
                    datetime.now(UTC)
                    + timedelta(seconds=self.capability_ttl_seconds)
                ),
            )
        return self._view(run, agent_id=agent_id, capability=capability)

    async def invoke(
        self,
        agent_id: str,
        body: PublicRunCreateRequest,
        *,
        idempotency_key: str | None,
        authorization: str | None,
    ) -> PublicRunView:
        if authorization is not None:
            raw = self._bearer(authorization)
            assert raw is not None
            await self._authenticate_api_key(
                raw,
                agent_id=agent_id,
                required_scope="runs:read",
            )
        created = await self.create_run(
            agent_id,
            body,
            idempotency_key=idempotency_key,
            authorization=authorization,
        )
        deadline = time.monotonic() + self.sync_wait_seconds
        current = created
        while (
            current.status.value not in TERMINAL_STATUSES
            and time.monotonic() < deadline
        ):
            await asyncio.sleep(self.poll_interval_seconds)
            current = await self.get_run(
                agent_id,
                UUID(current.run_id.root),
                authorization=(
                    f"Bearer {created.run_capability}"
                    if created.run_capability is not None
                    else authorization
                ),
            )
            if created.run_capability is not None:
                current = current.model_copy(
                    update={"run_capability": created.run_capability}
                )
        return current

    async def get_run(
        self,
        agent_id: str,
        run_id: UUID,
        *,
        authorization: str | None,
    ) -> PublicRunView:
        principal = await self._read_principal(
            agent_id=agent_id,
            run_id=run_id,
            authorization=authorization,
            required_scope="runs:read",
        )
        run = await self.run_service.get_run(run_id, self._scope(principal))
        if not self._run_belongs_to_agent(run, agent_id):
            raise ApiError(404, "run_not_found")
        return self._view(run, agent_id=agent_id)

    async def authorize_events(
        self,
        agent_id: str,
        run_id: UUID,
        *,
        authorization: str | None,
    ) -> None:
        principal = await self._read_principal(
            agent_id=agent_id,
            run_id=run_id,
            authorization=authorization,
            required_scope="events:read",
        )
        run = await self.run_service.get_run(run_id, self._scope(principal))
        if not self._run_belongs_to_agent(run, agent_id):
            raise ApiError(404, "run_not_found")

    @staticmethod
    def _sanitize_event(
        event: dict[str, Any],
        *,
        run: RunView,
    ) -> dict[str, Any]:
        event_type = str(event.get("type"))
        if event_type == "run.completed":
            public_type = "run.completed"
            status = "completed"
            output = run.output
            error_code = None
        elif event_type == "run.failed":
            public_type = "run.failed"
            status = "failed"
            output = None
            error_code = "invocation_unavailable"
        elif event_type == "run.cancelled":
            public_type = "run.cancelled"
            status = "cancelled"
            output = None
            error_code = "run_cancelled"
        elif event_type == "run.started":
            public_type = "run.started"
            status = "running"
            output = None
            error_code = None
        else:
            public_type = "run.progress"
            status = "running"
            output = None
            error_code = None
        return PublicRunEvent.model_validate(
            {
                "schema_version": "0.1.0",
                "sequence": int(event["sequence"]),
                "type": public_type,
                "status": status,
                "output": output,
                "error_code": error_code,
                "occurred_at": event["occurred_at"],
            }
        ).model_dump(mode="json")

    async def stream_events(
        self,
        request: Request,
        agent_id: str,
        run_id: UUID,
        *,
        authorization: str | None,
        after_sequence: int,
    ) -> AsyncIterator[bytes]:
        principal = await self._read_principal(
            agent_id=agent_id,
            run_id=run_id,
            authorization=authorization,
            required_scope="events:read",
        )
        scope = self._scope(principal)
        run = await self.run_service.get_run(run_id, scope)
        if not self._run_belongs_to_agent(run, agent_id):
            raise ApiError(404, "run_not_found")
        cursor = after_sequence
        last_write = time.monotonic() - self.heartbeat_seconds
        for _ in range(self.max_polls):
            if await request.is_disconnected():
                return
            events = await self.run_service.list_events(
                run_id,
                scope,
                after_sequence=cursor,
            )
            if events:
                run = await self.run_service.get_run(run_id, scope)
            for event in events:
                cursor = int(event["sequence"])
                public = self._sanitize_event(event, run=run)
                data = canonicalize(public).decode("utf-8")
                yield (
                    f"id: {cursor}\nevent: {public['type']}\n"
                    f"data: {data}\n\n"
                ).encode()
                last_write = time.monotonic()
                if str(event["type"]) in TERMINAL_EVENTS:
                    return
            if run.status in TERMINAL_STATUSES:
                return
            if time.monotonic() - last_write >= self.heartbeat_seconds:
                yield b": heartbeat\n\n"
                last_write = time.monotonic()
            await asyncio.sleep(self.poll_interval_seconds)
