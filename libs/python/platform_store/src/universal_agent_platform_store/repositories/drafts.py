"""Scoped mutable AgentDraft persistence."""

from __future__ import annotations

from typing import Any, cast
from uuid import UUID, uuid4

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from universal_agent_platform_store.models import (
    Agent,
    AgentActiveVersion,
    AgentDraftRecord,
    AgentVersion,
    utc_now,
)
from universal_agent_platform_store.repositories.base import ScopedRepository
from universal_agent_platform_store.scope import RequestScope


class DraftNotFound(RuntimeError):
    pass


class DraftRevisionConflict(RuntimeError):
    pass


class ActiveAgentVersionMissing(RuntimeError):
    pass


class DraftRepository(ScopedRepository):
    def __init__(
        self,
        session: AsyncSession,
        scope: RequestScope | None,
    ) -> None:
        super().__init__(session, scope)
        self.workspace_id, self.project_id = self.scope.tenant_ids()

    async def create_from_active(
        self,
        agent_key: str,
        layout: dict[str, Any],
    ) -> tuple[AgentDraftRecord, bool]:
        lock_key = (
            f"{self.workspace_id}:{self.project_id}:{agent_key}:draft"
        )
        await self.session.scalar(
            select(
                func.pg_advisory_xact_lock(
                    func.hashtextextended(lock_key, 0)
                )
            )
        )
        agent = await self._agent(agent_key)
        if agent is None:
            raise ActiveAgentVersionMissing("agent_version_not_active")
        existing = await self._draft_for_agent(agent.id)
        if existing is not None:
            return existing, False
        active_version = await self.session.scalar(
            select(AgentVersion)
            .join(
                AgentActiveVersion,
                AgentActiveVersion.version_id == AgentVersion.id,
            )
            .where(
                AgentVersion.workspace_id == self.workspace_id,
                AgentVersion.project_id == self.project_id,
                AgentVersion.agent_id == agent.id,
                AgentActiveVersion.workspace_id == self.workspace_id,
                AgentActiveVersion.project_id == self.project_id,
                AgentActiveVersion.agent_id == agent.id,
            )
        )
        if active_version is None:
            raise ActiveAgentVersionMissing("agent_version_not_active")
        record = AgentDraftRecord(
            id=uuid4(),
            workspace_id=self.workspace_id,
            project_id=self.project_id,
            agent_id=agent.id,
            base_version_id=active_version.id,
            revision=1,
            digest=active_version.digest,
            agent_spec=active_version.agent_spec,
            layout=layout,
            updated_by_owner_id=self.scope.owner_id,
        )
        self.session.add(record)
        await self.session.flush()
        return record, True

    async def get(self, agent_key: str) -> AgentDraftRecord | None:
        agent = await self._agent(agent_key)
        if agent is None:
            return None
        return await self._draft_for_agent(agent.id)

    async def update(
        self,
        agent_key: str,
        *,
        expected_revision: int,
        agent_spec: dict[str, Any],
        digest: str,
        layout: dict[str, Any],
    ) -> AgentDraftRecord:
        agent = await self._agent(agent_key)
        if agent is None:
            raise DraftNotFound("agent_draft_not_found")
        record = await self.session.scalar(
            select(AgentDraftRecord)
            .where(
                AgentDraftRecord.workspace_id == self.workspace_id,
                AgentDraftRecord.project_id == self.project_id,
                AgentDraftRecord.agent_id == agent.id,
            )
            .with_for_update()
        )
        if record is None:
            raise DraftNotFound("agent_draft_not_found")
        if record.revision != expected_revision:
            raise DraftRevisionConflict("agent_draft_revision_conflict")
        record.agent_spec = agent_spec
        record.digest = digest
        record.layout = layout
        record.revision += 1
        record.updated_by_owner_id = self.scope.owner_id
        record.updated_at = utc_now()
        await self.session.flush()
        return record

    async def _agent(self, agent_key: str) -> Agent | None:
        return cast(
            Agent | None,
            await self.session.scalar(
                select(Agent).where(
                    Agent.workspace_id == self.workspace_id,
                    Agent.project_id == self.project_id,
                    Agent.agent_key == agent_key,
                )
            ),
        )

    async def _draft_for_agent(
        self,
        agent_id: UUID,
    ) -> AgentDraftRecord | None:
        return cast(
            AgentDraftRecord | None,
            await self.session.scalar(
                select(AgentDraftRecord).where(
                    AgentDraftRecord.workspace_id == self.workspace_id,
                    AgentDraftRecord.project_id == self.project_id,
                    AgentDraftRecord.agent_id == agent_id,
                )
            ),
        )
