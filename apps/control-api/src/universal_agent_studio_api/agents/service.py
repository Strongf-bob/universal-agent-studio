"""Canonical validation and transactional AgentVersion operations."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any, cast
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from universal_agent_kernel.contracts.canonical import (
    CanonicalJsonError,
    content_digest,
    parse_json_document,
)
from universal_agent_kernel.contracts.validation import validate_agent_spec
from universal_agent_platform_store.repositories.agents import (
    ActiveVersionConflict,
    AgentRepository,
    AgentVersionNotFound,
)
from universal_agent_platform_store.scope import RequestScope

from universal_agent_studio_api.agents.models import (
    ActiveAgentVersionView,
    AgentVersionImportView,
    AgentVersionPersistence,
    AgentVersionView,
    StoredAgentVersion,
    ValidationIssueView,
    ValidationView,
)
from universal_agent_studio_api.errors import ApiError


class SqlAgentVersionPersistence:
    def __init__(
        self,
        *,
        session_factory: async_sessionmaker[AsyncSession] | None = None,
        session: AsyncSession | None = None,
    ) -> None:
        if (session_factory is None) == (session is None):
            raise ValueError("exactly_one_session_source_required")
        self._session_factory = session_factory
        self._session = session

    @classmethod
    def from_session(
        cls,
        session: AsyncSession,
    ) -> SqlAgentVersionPersistence:
        return cls(session=session)

    @classmethod
    def from_factory(
        cls,
        session_factory: async_sessionmaker[AsyncSession],
    ) -> SqlAgentVersionPersistence:
        return cls(session_factory=session_factory)

    @asynccontextmanager
    async def _transaction(self) -> AsyncIterator[AsyncSession]:
        if self._session is not None:
            try:
                yield self._session
                await self._session.commit()
            except Exception:
                await self._session.rollback()
                raise
            return

        assert self._session_factory is not None
        async with self._session_factory() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    @staticmethod
    def _stored(version: Any, agent_id: str) -> StoredAgentVersion:
        return StoredAgentVersion(
            id=version.id,
            agent_id=agent_id,
            schema_version=version.schema_version,
            digest=version.digest,
            agent_spec=cast(dict[str, Any], version.agent_spec),
        )

    async def import_version(
        self,
        *,
        scope: RequestScope,
        agent_spec: dict[str, Any],
        digest: str,
    ) -> tuple[StoredAgentVersion, bool]:
        async with self._transaction() as session:
            version, created = await AgentRepository(
                session,
                scope,
            ).import_version(agent_spec, digest)
            stored = self._stored(version, str(agent_spec["agent_id"]))
        return stored, created

    async def get_version(
        self,
        *,
        scope: RequestScope,
        version_id: UUID,
    ) -> StoredAgentVersion | None:
        async with self._transaction() as session:
            version = await AgentRepository(session, scope).get_version(version_id)
            if version is None:
                return None
            agent_id = str(version.agent_spec["agent_id"])
            stored = self._stored(version, agent_id)
        return stored

    async def activate(
        self,
        *,
        scope: RequestScope,
        agent_id: str,
        version_id: UUID,
        expected_previous_version_id: UUID | None,
    ) -> UUID:
        async with self._transaction() as session:
            active = await AgentRepository(session, scope).activate(
                agent_key=agent_id,
                version_id=version_id,
                expected_previous_version_id=expected_previous_version_id,
            )
            active_version_id = active.version_id
        return active_version_id


class AgentVersionService:
    def __init__(
        self,
        persistence: AgentVersionPersistence,
        *,
        max_document_bytes: int = 1_048_576,
    ) -> None:
        self.persistence = persistence
        self.max_document_bytes = max_document_bytes

    @staticmethod
    def _validation_view(result: Any) -> ValidationView:
        return ValidationView(
            valid=result.valid,
            issues=[
                ValidationIssueView(
                    code=issue.code,
                    json_pointer=issue.json_pointer,
                    node_id=issue.node_id,
                    message_key=issue.message_key,
                )
                for issue in result.issues
            ],
        )

    async def import_raw(
        self,
        raw: bytes,
        scope: RequestScope,
    ) -> AgentVersionImportView:
        if len(raw) > self.max_document_bytes:
            raise ApiError(413, "request_too_large")
        try:
            parsed = parse_json_document(raw)
        except CanonicalJsonError as error:
            raise ApiError(422, error.code) from error
        if not isinstance(parsed, dict):
            raise ApiError(
                422,
                "agent_spec_invalid",
                details={
                    "validation": {
                        "valid": False,
                        "issues": [
                            {
                                "code": "schema_validation_failed",
                                "json_pointer": "",
                                "node_id": None,
                                "message_key": "validation.schema.type",
                            }
                        ],
                    }
                },
            )

        document = cast(dict[str, Any], parsed)
        validation = validate_agent_spec(document)
        validation_view = self._validation_view(validation)
        if not validation.valid:
            raise ApiError(
                422,
                "agent_spec_invalid",
                details={"validation": validation_view.model_dump()},
            )

        digest = content_digest(document)
        stored, created = await self.persistence.import_version(
            scope=scope,
            agent_spec=document,
            digest=digest,
        )
        return AgentVersionImportView(
            version_id=str(stored.id),
            agent_id=stored.agent_id,
            schema_version=stored.schema_version,
            digest=stored.digest,
            validation=validation_view,
            reused=not created,
        )

    async def get_version(
        self,
        version_id: UUID,
        scope: RequestScope,
    ) -> AgentVersionView:
        stored = await self.persistence.get_version(
            scope=scope,
            version_id=version_id,
        )
        if stored is None:
            raise ApiError(404, "agent_version_not_found")
        return AgentVersionView(
            version_id=str(stored.id),
            agent_id=stored.agent_id,
            schema_version=stored.schema_version,
            digest=stored.digest,
            agent_spec=stored.agent_spec,
        )

    async def activate(
        self,
        *,
        agent_id: str,
        version_id: UUID,
        expected_previous_version_id: UUID | None,
        scope: RequestScope,
    ) -> ActiveAgentVersionView:
        try:
            active_version_id = await self.persistence.activate(
                scope=scope,
                agent_id=agent_id,
                version_id=version_id,
                expected_previous_version_id=expected_previous_version_id,
            )
        except ActiveVersionConflict as error:
            raise ApiError(409, "active_version_changed") from error
        except AgentVersionNotFound as error:
            raise ApiError(404, "agent_version_not_found") from error
        return ActiveAgentVersionView(
            agent_id=agent_id,
            active_version_id=str(active_version_id),
        )
