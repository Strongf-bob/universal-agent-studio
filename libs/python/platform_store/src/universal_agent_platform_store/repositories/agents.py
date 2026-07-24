"""Scoped immutable AgentVersion persistence."""

from __future__ import annotations

from typing import Any, cast
from uuid import UUID, uuid4

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from universal_agent_platform_store.models import (
    Agent,
    AgentActiveVersion,
    AgentVersion,
)
from universal_agent_platform_store.repositories.base import ScopedRepository
from universal_agent_platform_store.scope import RequestScope


class ActiveVersionConflict(RuntimeError):
    pass


class AgentVersionNotFound(RuntimeError):
    pass


class AgentRepository(ScopedRepository):
    def __init__(
        self,
        session: AsyncSession,
        scope: RequestScope | None,
    ) -> None:
        super().__init__(session, scope)
        self.workspace_id, self.project_id = self.scope.tenant_ids()

    async def import_version(
        self,
        agent_spec: dict[str, Any],
        digest: str,
        *,
        provenance: dict[str, Any] | None = None,
    ) -> tuple[AgentVersion, bool]:
        agent_key = str(agent_spec["agent_id"])
        lock_key = f"{self.workspace_id}:{self.project_id}:{agent_key}"
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
            agent = Agent(
                id=uuid4(),
                workspace_id=self.workspace_id,
                project_id=self.project_id,
                agent_key=agent_key,
                localized_metadata=agent_spec["localized_metadata"],
            )
            self.session.add(agent)
            await self.session.flush()

        existing = await self.session.scalar(
            select(AgentVersion).where(
                AgentVersion.workspace_id == self.workspace_id,
                AgentVersion.project_id == self.project_id,
                AgentVersion.agent_id == agent.id,
                AgentVersion.digest == digest,
            )
        )
        if existing is not None:
            return existing, False

        next_version = await self.session.scalar(
            select(func.coalesce(func.max(AgentVersion.version_number), 0) + 1).where(
                AgentVersion.agent_id == agent.id
            )
        )
        version = AgentVersion(
            id=uuid4(),
            workspace_id=self.workspace_id,
            project_id=self.project_id,
            agent_id=agent.id,
            version_number=int(next_version or 1),
            schema_version=str(agent_spec["schema_version"]),
            digest=digest,
            agent_spec=agent_spec,
            provenance=provenance or {},
            created_by_owner_id=self.scope.owner_id,
        )
        self.session.add(version)
        await self.session.flush()
        return version, True

    async def activate(
        self,
        *,
        agent_key: str,
        version_id: UUID,
        expected_previous_version_id: UUID | None,
    ) -> AgentActiveVersion:
        agent = await self.session.scalar(
            select(Agent).where(
                Agent.workspace_id == self.workspace_id,
                Agent.project_id == self.project_id,
                Agent.agent_key == agent_key,
            )
        )
        if agent is None:
            raise AgentVersionNotFound("agent_not_found")

        version = await self.session.scalar(
            select(AgentVersion).where(
                AgentVersion.id == version_id,
                AgentVersion.workspace_id == self.workspace_id,
                AgentVersion.project_id == self.project_id,
                AgentVersion.agent_id == agent.id,
            )
        )
        if version is None:
            raise AgentVersionNotFound("agent_version_not_found")

        active = await self.session.scalar(
            select(AgentActiveVersion)
            .where(
                AgentActiveVersion.agent_id == agent.id,
                AgentActiveVersion.workspace_id == self.workspace_id,
                AgentActiveVersion.project_id == self.project_id,
            )
            .with_for_update()
        )
        current_id = active.version_id if active is not None else None
        if current_id != expected_previous_version_id:
            raise ActiveVersionConflict("active_version_changed")

        if active is None:
            active = AgentActiveVersion(
                agent_id=agent.id,
                workspace_id=self.workspace_id,
                project_id=self.project_id,
                version_id=version.id,
            )
            self.session.add(active)
        else:
            active.version_id = version.id
        await self.session.flush()
        return active

    async def get_version(self, version_id: UUID) -> AgentVersion | None:
        return cast(
            AgentVersion | None,
            await self.session.scalar(
                select(AgentVersion).where(
                    AgentVersion.id == version_id,
                    AgentVersion.workspace_id == self.workspace_id,
                    AgentVersion.project_id == self.project_id,
                )
            ),
        )

    async def get_version_by_public_id(
        self,
        version_id: str,
    ) -> AgentVersion | None:
        agent_key, separator, raw_number = version_id.rpartition("-v")
        if not separator or not raw_number.isdigit():
            return None
        return cast(
            AgentVersion | None,
            await self.session.scalar(
                select(AgentVersion)
                .join(Agent, Agent.id == AgentVersion.agent_id)
                .where(
                    AgentVersion.workspace_id == self.workspace_id,
                    AgentVersion.project_id == self.project_id,
                    AgentVersion.version_number == int(raw_number),
                    Agent.agent_key == agent_key,
                )
            ),
        )

    async def get_active_version_by_public_id(
        self,
        version_id: str,
    ) -> AgentVersion | None:
        version = await self.get_version_by_public_id(version_id)
        if version is None:
            return None
        active = await self.session.scalar(
            select(AgentActiveVersion).where(
                AgentActiveVersion.workspace_id == self.workspace_id,
                AgentActiveVersion.project_id == self.project_id,
                AgentActiveVersion.agent_id == version.agent_id,
                AgentActiveVersion.version_id == version.id,
            )
        )
        return version if active is not None else None
