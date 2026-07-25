"""Scoped publication, rollback and API-key persistence."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from typing import Any, cast
from uuid import UUID, uuid4

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from universal_agent_platform_store.models import (
    Agent,
    AgentActiveVersion,
    AgentApiKey,
    AgentDraftRecord,
    AgentPublicationEvent,
    AgentVersion,
    utc_now,
)
from universal_agent_platform_store.repositories.base import ScopedRepository
from universal_agent_platform_store.repositories.drafts import (
    DraftRevisionConflict as DraftRevisionConflict,
)
from universal_agent_platform_store.scope import RequestScope


class PublicationNotFound(RuntimeError):
    pass


class ActiveVersionConflict(RuntimeError):
    pass


class DraftValidationFailed(RuntimeError):
    pass


@dataclass(frozen=True)
class PublicationResult:
    version: AgentVersion
    previous_version_id: UUID | None
    event: AgentPublicationEvent | None
    reused: bool


@dataclass(frozen=True)
class PublishingStateRecord:
    agent: Agent
    draft: AgentDraftRecord
    active_version: AgentVersion | None
    versions: tuple[AgentVersion, ...]
    events: tuple[AgentPublicationEvent, ...]


class PublishingRepository(ScopedRepository):
    def __init__(
        self,
        session: AsyncSession,
        scope: RequestScope | None,
    ) -> None:
        super().__init__(session, scope)
        self.workspace_id, self.project_id = self.scope.tenant_ids()

    async def _lock_agent(self, agent_key: str) -> Agent:
        lock_key = f"{self.workspace_id}:{self.project_id}:{agent_key}:publish"
        await self.session.scalar(
            select(
                func.pg_advisory_xact_lock(
                    func.hashtextextended(lock_key, 0)
                )
            )
        )
        agent = await self.session.scalar(
            select(Agent).where(
                Agent.workspace_id == self.workspace_id,
                Agent.project_id == self.project_id,
                Agent.agent_key == agent_key,
            )
        )
        if agent is None:
            raise PublicationNotFound("agent_not_found")
        return agent

    async def _locked_draft(self, agent_id: UUID) -> AgentDraftRecord:
        draft = await self.session.scalar(
            select(AgentDraftRecord)
            .where(
                AgentDraftRecord.workspace_id == self.workspace_id,
                AgentDraftRecord.project_id == self.project_id,
                AgentDraftRecord.agent_id == agent_id,
            )
            .with_for_update()
        )
        if draft is None:
            raise PublicationNotFound("agent_draft_not_found")
        return draft

    async def _locked_active(
        self,
        agent_id: UUID,
    ) -> AgentActiveVersion | None:
        return cast(
            AgentActiveVersion | None,
            await self.session.scalar(
                select(AgentActiveVersion)
                .where(
                    AgentActiveVersion.workspace_id == self.workspace_id,
                    AgentActiveVersion.project_id == self.project_id,
                    AgentActiveVersion.agent_id == agent_id,
                )
                .with_for_update()
            ),
        )

    @staticmethod
    def _check_active(
        active: AgentActiveVersion | None,
        expected_active_version_id: UUID | None,
    ) -> UUID | None:
        current = active.version_id if active is not None else None
        if current != expected_active_version_id:
            raise ActiveVersionConflict("active_version_changed")
        return current

    async def publish_draft(
        self,
        agent_key: str,
        *,
        expected_revision: int,
        expected_active_version_id: UUID | None,
        validate_draft: Callable[[dict[str, Any]], bool] | None = None,
    ) -> PublicationResult:
        agent = await self._lock_agent(agent_key)
        draft = await self._locked_draft(agent.id)
        if draft.revision != expected_revision:
            raise DraftRevisionConflict("agent_draft_revision_conflict")
        if validate_draft is not None and not validate_draft(draft.agent_spec):
            raise DraftValidationFailed("agent_spec_invalid")
        active = await self._locked_active(agent.id)
        previous = self._check_active(active, expected_active_version_id)

        version = await self.session.scalar(
            select(AgentVersion).where(
                AgentVersion.workspace_id == self.workspace_id,
                AgentVersion.project_id == self.project_id,
                AgentVersion.agent_id == agent.id,
                AgentVersion.digest == draft.digest,
            )
        )
        reused = version is not None
        if version is None:
            next_number = await self.session.scalar(
                select(
                    func.coalesce(func.max(AgentVersion.version_number), 0) + 1
                ).where(AgentVersion.agent_id == agent.id)
            )
            version = AgentVersion(
                id=uuid4(),
                workspace_id=self.workspace_id,
                project_id=self.project_id,
                agent_id=agent.id,
                version_number=int(next_number or 1),
                schema_version=str(draft.agent_spec["schema_version"]),
                digest=draft.digest,
                agent_spec=draft.agent_spec,
                provenance={
                    "kind": "publication",
                    "draft_id": str(draft.id),
                    "draft_revision": draft.revision,
                },
                created_by_owner_id=self.scope.owner_id,
            )
            self.session.add(version)
            await self.session.flush()

        already_active = previous == version.id
        if already_active:
            existing_publication = await self.session.scalar(
                select(AgentPublicationEvent.id)
                .where(
                    AgentPublicationEvent.workspace_id == self.workspace_id,
                    AgentPublicationEvent.project_id == self.project_id,
                    AgentPublicationEvent.agent_id == agent.id,
                    AgentPublicationEvent.event_type == "publish",
                )
                .limit(1)
            )
            if existing_publication is not None:
                return PublicationResult(
                    version=version,
                    previous_version_id=previous,
                    event=None,
                    reused=True,
                )
        elif active is None:
            active = AgentActiveVersion(
                agent_id=agent.id,
                workspace_id=self.workspace_id,
                project_id=self.project_id,
                version_id=version.id,
            )
            self.session.add(active)
        elif active is not None:
            active.version_id = version.id
            active.updated_at = utc_now()
        event = AgentPublicationEvent(
            id=uuid4(),
            workspace_id=self.workspace_id,
            project_id=self.project_id,
            agent_id=agent.id,
            event_type="publish",
            previous_version_id=previous,
            selected_version_id=version.id,
            selected_version_digest=version.digest,
            actor_owner_id=self.scope.owner_id,
        )
        self.session.add(event)
        await self.session.flush()
        return PublicationResult(
            version=version,
            previous_version_id=previous,
            event=event,
            reused=reused,
        )

    async def rollback(
        self,
        agent_key: str,
        *,
        target_version_id: UUID,
        expected_active_version_id: UUID,
    ) -> PublicationResult:
        agent = await self._lock_agent(agent_key)
        active = await self._locked_active(agent.id)
        previous = self._check_active(active, expected_active_version_id)
        if active is None:
            raise ActiveVersionConflict("active_version_changed")
        target = await self.session.scalar(
            select(AgentVersion).where(
                AgentVersion.id == target_version_id,
                AgentVersion.workspace_id == self.workspace_id,
                AgentVersion.project_id == self.project_id,
                AgentVersion.agent_id == agent.id,
            )
        )
        if target is None:
            raise PublicationNotFound("agent_version_not_found")
        if previous == target.id:
            return PublicationResult(
                version=target,
                previous_version_id=previous,
                event=None,
                reused=True,
            )
        active.version_id = target.id
        active.updated_at = utc_now()
        event = AgentPublicationEvent(
            id=uuid4(),
            workspace_id=self.workspace_id,
            project_id=self.project_id,
            agent_id=agent.id,
            event_type="rollback",
            previous_version_id=previous,
            selected_version_id=target.id,
            selected_version_digest=target.digest,
            actor_owner_id=self.scope.owner_id,
        )
        self.session.add(event)
        await self.session.flush()
        return PublicationResult(
            version=target,
            previous_version_id=previous,
            event=event,
            reused=True,
        )

    async def get_state(self, agent_key: str) -> PublishingStateRecord | None:
        agent = await self.session.scalar(
            select(Agent).where(
                Agent.workspace_id == self.workspace_id,
                Agent.project_id == self.project_id,
                Agent.agent_key == agent_key,
            )
        )
        if agent is None:
            return None
        draft = await self.session.scalar(
            select(AgentDraftRecord).where(
                AgentDraftRecord.workspace_id == self.workspace_id,
                AgentDraftRecord.project_id == self.project_id,
                AgentDraftRecord.agent_id == agent.id,
            )
        )
        if draft is None:
            return None
        active_version = await self.session.scalar(
            select(AgentVersion)
            .join(
                AgentActiveVersion,
                AgentActiveVersion.version_id == AgentVersion.id,
            )
            .where(
                AgentActiveVersion.workspace_id == self.workspace_id,
                AgentActiveVersion.project_id == self.project_id,
                AgentActiveVersion.agent_id == agent.id,
            )
        )
        versions = tuple(
            await self.session.scalars(
                select(AgentVersion)
                .where(
                    AgentVersion.workspace_id == self.workspace_id,
                    AgentVersion.project_id == self.project_id,
                    AgentVersion.agent_id == agent.id,
                )
                .order_by(AgentVersion.version_number.desc())
            )
        )
        events = tuple(
            await self.session.scalars(
                select(AgentPublicationEvent)
                .where(
                    AgentPublicationEvent.workspace_id == self.workspace_id,
                    AgentPublicationEvent.project_id == self.project_id,
                    AgentPublicationEvent.agent_id == agent.id,
                )
                .order_by(
                    AgentPublicationEvent.created_at.desc(),
                    AgentPublicationEvent.id.desc(),
                )
            )
        )
        return PublishingStateRecord(
            agent=agent,
            draft=draft,
            active_version=active_version,
            versions=versions,
            events=events,
        )


class ApiKeyRepository(ScopedRepository):
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
            raise PublicationNotFound("agent_not_found")
        return agent

    async def create(
        self,
        agent_key: str,
        *,
        label: str,
        prefix: str,
        key_hash: str,
        scopes: list[str],
        expires_at: datetime | None,
    ) -> AgentApiKey:
        agent = await self._agent(agent_key)
        record = AgentApiKey(
            id=uuid4(),
            workspace_id=self.workspace_id,
            project_id=self.project_id,
            agent_id=agent.id,
            label=label,
            prefix=prefix,
            key_hash=key_hash,
            scopes=scopes,
            expires_at=expires_at,
        )
        self.session.add(record)
        await self.session.flush()
        return record

    async def list(self, agent_key: str) -> tuple[AgentApiKey, ...]:
        agent = await self._agent(agent_key)
        return tuple(
            await self.session.scalars(
                select(AgentApiKey)
                .where(
                    AgentApiKey.workspace_id == self.workspace_id,
                    AgentApiKey.project_id == self.project_id,
                    AgentApiKey.agent_id == agent.id,
                )
                .order_by(AgentApiKey.created_at.desc())
            )
        )

    async def revoke(
        self,
        agent_key: str,
        key_id: UUID,
    ) -> AgentApiKey | None:
        agent = await self._agent(agent_key)
        record = await self.session.scalar(
            select(AgentApiKey)
            .where(
                AgentApiKey.id == key_id,
                AgentApiKey.workspace_id == self.workspace_id,
                AgentApiKey.project_id == self.project_id,
                AgentApiKey.agent_id == agent.id,
            )
            .with_for_update()
        )
        if record is not None and record.revoked_at is None:
            record.revoked_at = utc_now()
            await self.session.flush()
        return record
