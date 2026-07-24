"""Canonical AgentDraft validation, persistence and diff behavior."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from universal_agent_kernel.contracts.canonical import content_digest
from universal_agent_kernel.contracts.validation import (
    ValidationIssue,
    ValidationResult,
    validate_agent_spec,
)
from universal_agent_kernel.redaction.policy import DefaultRedactionPolicy
from universal_agent_platform_store.models import (
    Agent,
    AgentDraftRecord,
    AgentVersion,
)
from universal_agent_platform_store.repositories.drafts import (
    ActiveAgentVersionMissing,
    DraftNotFound,
    DraftRepository,
    DraftRevisionConflict,
)
from universal_agent_platform_store.scope import RequestScope

from universal_agent_studio_api.agents.drafts import (
    AgentDraftPersistence,
    AgentDraftView,
    DraftDiffOperationView,
    DraftDiffRequest,
    DraftDiffView,
    DraftLayoutView,
    DraftNodePositionView,
    DraftTestRunRequest,
    DraftViewportView,
    StoredAgentDraft,
    UpdateAgentDraftRequest,
)
from universal_agent_studio_api.agents.models import (
    AgentVersionPersistence,
    ValidationIssueView,
    ValidationView,
)
from universal_agent_studio_api.errors import ApiError
from universal_agent_studio_api.runs.service import (
    CreateRunRequest,
    CreateRunView,
    RunService,
)


def _validation_view(result: ValidationResult) -> ValidationView:
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


def default_layout(agent_spec: dict[str, Any]) -> DraftLayoutView:
    nodes = [
        DraftNodePositionView(
            node_id=str(node["id"]),
            x=index * 260,
            y=80 if index % 2 == 0 else 200,
        )
        for index, node in enumerate(agent_spec.get("nodes", []))
        if isinstance(node, dict) and isinstance(node.get("id"), str)
    ]
    return DraftLayoutView(
        nodes=nodes,
        viewport=DraftViewportView(x=0, y=0, zoom=1),
    )


class SqlAgentDraftPersistence:
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
    ) -> SqlAgentDraftPersistence:
        return cls(session=session)

    @classmethod
    def from_factory(
        cls,
        session_factory: async_sessionmaker[AsyncSession],
    ) -> SqlAgentDraftPersistence:
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
    async def _stored(
        session: AsyncSession,
        record: AgentDraftRecord,
    ) -> StoredAgentDraft:
        version = await session.scalar(
            select(AgentVersion).where(
                AgentVersion.id == record.base_version_id,
                AgentVersion.workspace_id == record.workspace_id,
                AgentVersion.project_id == record.project_id,
            )
        )
        agent_key = await session.scalar(
            select(Agent.agent_key).where(
                Agent.id == record.agent_id,
                Agent.workspace_id == record.workspace_id,
                Agent.project_id == record.project_id,
            )
        )
        if version is None or agent_key is None:
            raise RuntimeError("agent_draft_relations_missing")
        return StoredAgentDraft(
            id=record.id,
            agent_id=agent_key,
            revision=record.revision,
            base_version_id=f"{agent_key}-v{version.version_number}",
            digest=record.digest,
            agent_spec=record.agent_spec,
            layout=record.layout,
            updated_at=record.updated_at,
        )

    async def create(
        self,
        *,
        scope: RequestScope,
        agent_id: str,
    ) -> tuple[StoredAgentDraft, bool]:
        async with self._transaction() as session:
            record, created = await DraftRepository(
                session,
                scope,
            ).create_from_active(
                agent_id,
                {
                    "nodes": [],
                    "viewport": {"x": 0, "y": 0, "zoom": 1},
                },
            )
            if created:
                record.layout = default_layout(record.agent_spec).model_dump()
                await session.flush()
            stored = await self._stored(session, record)
        return stored, created

    async def get(
        self,
        *,
        scope: RequestScope,
        agent_id: str,
    ) -> StoredAgentDraft | None:
        async with self._transaction() as session:
            record = await DraftRepository(session, scope).get(agent_id)
            if record is None:
                return None
            stored = await self._stored(session, record)
        return stored

    async def update(
        self,
        *,
        scope: RequestScope,
        agent_id: str,
        expected_revision: int,
        agent_spec: dict[str, Any],
        digest: str,
        layout: dict[str, Any],
    ) -> StoredAgentDraft:
        async with self._transaction() as session:
            record = await DraftRepository(session, scope).update(
                agent_id,
                expected_revision=expected_revision,
                agent_spec=agent_spec,
                digest=digest,
                layout=layout,
            )
            stored = await self._stored(session, record)
        return stored


class DraftService:
    def __init__(
        self,
        persistence: AgentDraftPersistence,
        *,
        agent_persistence: AgentVersionPersistence | None = None,
        run_service: RunService | None = None,
    ) -> None:
        self.persistence = persistence
        self.agent_persistence = agent_persistence
        self.run_service = run_service

    @staticmethod
    def _view(stored: StoredAgentDraft) -> AgentDraftView:
        return AgentDraftView(
            draft_id=stored.public_id,
            agent_id=stored.agent_id,
            revision=stored.revision,
            base_version_id=stored.base_version_id,
            digest=stored.digest,
            agent_spec=stored.agent_spec,
            layout=DraftLayoutView.model_validate(stored.layout),
            updated_at=stored.updated_at,
        )

    async def create(
        self,
        agent_id: str,
        scope: RequestScope,
    ) -> tuple[AgentDraftView, bool]:
        active = await self.persistence.get(
            scope=scope,
            agent_id=agent_id,
        )
        if active is not None:
            return self._view(active), False
        try:
            stored, created = await self.persistence.create(
                scope=scope,
                agent_id=agent_id,
            )
        except ActiveAgentVersionMissing as error:
            raise ApiError(404, "agent_version_not_active") from error
        return self._view(stored), created

    async def get(
        self,
        agent_id: str,
        scope: RequestScope,
    ) -> AgentDraftView:
        stored = await self._stored(agent_id, scope)
        return self._view(stored)

    async def update(
        self,
        agent_id: str,
        request: UpdateAgentDraftRequest,
        scope: RequestScope,
    ) -> AgentDraftView:
        self._validate_candidate(agent_id, request.agent_spec, request.layout)
        digest = content_digest(request.agent_spec)
        try:
            stored = await self.persistence.update(
                scope=scope,
                agent_id=agent_id,
                expected_revision=request.expected_revision,
                agent_spec=request.agent_spec,
                digest=digest,
                layout=request.layout.model_dump(),
            )
        except DraftRevisionConflict as error:
            raise ApiError(
                409,
                "agent_draft_revision_conflict",
            ) from error
        except DraftNotFound as error:
            raise ApiError(404, "agent_draft_not_found") from error
        return self._view(stored)

    async def preview_diff(
        self,
        agent_id: str,
        request: DraftDiffRequest,
        scope: RequestScope,
    ) -> DraftDiffView:
        stored = await self._stored(agent_id, scope)
        if stored.revision != request.expected_revision:
            raise ApiError(409, "agent_draft_revision_conflict")
        validation = self._validate_candidate(
            agent_id,
            request.candidate_agent_spec,
            DraftLayoutView.model_validate(stored.layout),
        )
        operations = _diff_documents(
            stored.agent_spec,
            request.candidate_agent_spec,
        )
        return DraftDiffView(
            draft_id=stored.public_id,
            revision=stored.revision,
            candidate_digest=content_digest(request.candidate_agent_spec),
            validation=_validation_view(validation),
            operations=operations,
        )

    async def create_test_run(
        self,
        agent_id: str,
        request: DraftTestRunRequest,
        scope: RequestScope,
    ) -> CreateRunView:
        if self.agent_persistence is None or self.run_service is None:
            raise ApiError(
                503,
                "durable_execution_unavailable",
                retryable=True,
            )
        stored = await self._stored(agent_id, scope)
        if stored.revision != request.expected_revision:
            raise ApiError(409, "agent_draft_revision_conflict")
        version, _ = await self.agent_persistence.import_version(
            scope=scope,
            agent_spec=stored.agent_spec,
            digest=stored.digest,
            provenance={
                "kind": "draft-test-snapshot",
                "draft_id": stored.public_id,
                "draft_revision": stored.revision,
                "draft_digest": stored.digest,
            },
        )
        return await self.run_service.create_resolved_run(
            CreateRunRequest(
                schema_version="0.1.0",
                request_id=request.request_id,
                agent_version_id=version.public_id,
                agent_version_digest=version.digest,
                idempotency_key=request.idempotency_key,
                input=request.input,
                locale=request.locale,
            ),
            scope,
            version,
        )

    async def _stored(
        self,
        agent_id: str,
        scope: RequestScope,
    ) -> StoredAgentDraft:
        stored = await self.persistence.get(
            scope=scope,
            agent_id=agent_id,
        )
        if stored is None:
            raise ApiError(404, "agent_draft_not_found")
        return stored

    @staticmethod
    def _validate_candidate(
        agent_id: str,
        agent_spec: dict[str, Any],
        layout: DraftLayoutView,
    ) -> ValidationResult:
        validation = validate_agent_spec(agent_spec)
        issues = list(validation.issues)
        if agent_spec.get("agent_id") != agent_id:
            issues.append(
                ValidationIssue(
                    code="agent_id_mismatch",
                    json_pointer="/agent_id",
                    node_id=None,
                    message_key="validation.semantic.agent_id_mismatch",
                )
            )
        spec_node_ids = {
            str(node["id"])
            for node in agent_spec.get("nodes", [])
            if isinstance(node, dict) and isinstance(node.get("id"), str)
        }
        for index, position in enumerate(layout.nodes):
            if position.node_id not in spec_node_ids:
                issues.append(
                    ValidationIssue(
                        code="dangling_layout_node_reference",
                        json_pointer=f"/layout/nodes/{index}/node_id",
                        node_id=position.node_id,
                        message_key=(
                            "validation.semantic."
                            "dangling_layout_node_reference"
                        ),
                    )
                )
        ordered = tuple(
            sorted(
                issues,
                key=lambda item: (
                    item.json_pointer,
                    item.code,
                    item.node_id or "",
                ),
            )
        )
        result = ValidationResult(valid=not ordered, issues=ordered)
        if not result.valid:
            raise ApiError(
                422,
                "agent_spec_invalid",
                details={
                    "validation": _validation_view(result).model_dump(),
                },
            )
        return result


def _pointer_part(value: str) -> str:
    return value.replace("~", "~0").replace("/", "~1")


def _diff_documents(
    before: Any,
    after: Any,
    pointer: str = "",
) -> list[DraftDiffOperationView]:
    redactor = DefaultRedactionPolicy()
    if isinstance(before, dict) and isinstance(after, dict):
        operations: list[DraftDiffOperationView] = []
        for key in sorted(set(before) | set(after)):
            child_pointer = f"{pointer}/{_pointer_part(str(key))}"
            if key not in before:
                operations.append(
                    DraftDiffOperationView(
                        op="add",
                        json_pointer=child_pointer,
                        after=redactor.redact(after[key]),
                    )
                )
            elif key not in after:
                operations.append(
                    DraftDiffOperationView(
                        op="remove",
                        json_pointer=child_pointer,
                        before=redactor.redact(before[key]),
                    )
                )
            else:
                operations.extend(
                    _diff_documents(
                        before[key],
                        after[key],
                        child_pointer,
                    )
                )
        return operations
    if before == after:
        return []
    return [
        DraftDiffOperationView(
            op="replace",
            json_pointer=pointer,
            before=redactor.redact(before),
            after=redactor.redact(after),
        )
    ]
