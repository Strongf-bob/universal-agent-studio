"""Idempotent run application service and PostgreSQL adapter."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Annotated, Any, Literal, Protocol, cast
from uuid import UUID, uuid5

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from universal_agent_kernel.contracts.canonical import content_digest
from universal_agent_kernel.contracts.validation import validate_agent_input
from universal_agent_kernel.domain import ExecutionCommand, RunEvent
from universal_agent_platform_store.models import (
    Agent,
    AgentVersion,
    Run,
    RunRequest,
    RunTraceRecord,
)
from universal_agent_platform_store.repositories.runs import (
    IdempotencyConflict,
    RunRepository,
)
from universal_agent_platform_store.repositories.webhooks import (
    WebhookRepository,
)
from universal_agent_platform_store.scope import RequestScope

from universal_agent_studio_api.agents.models import (
    AgentVersionPersistence,
    StoredAgentVersion,
)
from universal_agent_studio_api.errors import ApiError
from universal_agent_studio_api.runs.durable import (
    CancellationStatus,
    DurableExecutionPort,
)

TERMINAL_STATUSES = {"completed", "failed", "cancelled"}
TERMINAL_EVENTS = {"run.completed", "run.failed", "run.cancelled"}
Locale = Literal["ru-RU", "en-US"]
RunStatus = Literal["queued", "running", "completed", "failed", "cancelled"]


class CreateRunRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["0.1.0"]
    request_id: UUID
    agent_version_id: Annotated[
        str,
        Field(pattern=r"^[a-z][a-z0-9_-]{2,63}$"),
    ]
    agent_version_digest: Annotated[
        str,
        Field(pattern=r"^[0-9a-f]{64}$"),
    ]
    idempotency_key: Annotated[
        str,
        Field(pattern=r"^[A-Za-z0-9._:-]{16,128}$"),
    ]
    input: dict[str, Any]
    locale: Locale


@dataclass(frozen=True)
class RunCreateData:
    request_id: UUID
    agent_version_internal_id: UUID
    agent_version_id: str
    agent_version_digest: str
    idempotency_key: str
    input: dict[str, Any]
    locale: Locale


@dataclass(frozen=True)
class StoredRun:
    id: UUID
    request_id: UUID
    workspace_id: UUID
    project_id: UUID
    agent_version_internal_id: UUID
    agent_version_id: str
    agent_version_digest: str
    status: RunStatus
    locale: Locale
    input: dict[str, Any]
    output: dict[str, Any] | None
    durable_execution_id: str | None
    cancel_requested: bool


class CreateRunView(BaseModel):
    run_id: UUID
    request_id: UUID
    status: RunStatus
    reused: bool


class RunView(BaseModel):
    run_id: UUID
    request_id: UUID
    agent_version_id: str
    agent_version_digest: str
    status: RunStatus
    locale: Locale
    input: dict[str, Any]
    output: dict[str, Any] | None
    durable_execution_id: str | None
    cancel_requested: bool


class CancelRunView(BaseModel):
    run_id: UUID
    status: CancellationStatus


class RunPersistence(Protocol):
    async def create_idempotent(
        self,
        *,
        scope: RequestScope,
        data: RunCreateData,
        request_digest: str,
    ) -> tuple[StoredRun, bool]: ...

    async def set_durable_execution_id(
        self,
        *,
        scope: RequestScope,
        run_id: UUID,
        durable_execution_id: str,
    ) -> None: ...

    async def get_run(
        self,
        *,
        scope: RequestScope,
        run_id: UUID,
    ) -> StoredRun | None: ...

    async def request_cancel(
        self,
        *,
        scope: RequestScope,
        run_id: UUID,
    ) -> StoredRun | None: ...

    async def list_events(
        self,
        *,
        scope: RequestScope,
        run_id: UUID,
        after_sequence: int,
    ) -> list[dict[str, Any]]: ...

    async def get_trace(
        self,
        *,
        scope: RequestScope,
        run_id: UUID,
    ) -> dict[str, Any] | None: ...

    async def finalize_start_failure(
        self,
        *,
        scope: RequestScope,
        run: StoredRun,
        error_code: str,
    ) -> None: ...


class SqlRunPersistence:
    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
    ) -> None:
        self.session_factory = session_factory

    @staticmethod
    async def _stored(
        session: AsyncSession,
        run: Run,
    ) -> StoredRun:
        request_id = await session.scalar(
            select(RunRequest.id).where(RunRequest.resolved_run_id == run.id)
        )
        version = await session.scalar(
            select(AgentVersion).where(AgentVersion.id == run.agent_version_id)
        )
        if request_id is None or version is None:
            raise RuntimeError("run_relations_missing")
        agent_key = await session.scalar(
            select(Agent.agent_key).where(Agent.id == version.agent_id)
        )
        if agent_key is None:
            raise RuntimeError("run_agent_missing")
        return StoredRun(
            id=run.id,
            request_id=request_id,
            workspace_id=run.workspace_id,
            project_id=run.project_id,
            agent_version_internal_id=version.id,
            agent_version_id=f"{agent_key}-v{version.version_number}",
            agent_version_digest=version.digest,
            status=cast(RunStatus, run.status),
            locale=cast(Locale, run.locale),
            input=run.input_document,
            output=run.output_document,
            durable_execution_id=run.durable_execution_id,
            cancel_requested=run.cancel_requested,
        )

    async def create_idempotent(
        self,
        *,
        scope: RequestScope,
        data: RunCreateData,
        request_digest: str,
    ) -> tuple[StoredRun, bool]:
        async with self.session_factory() as session:
            try:
                run, created = await RunRepository(
                    session,
                    scope,
                ).create_idempotent(
                    request_id=data.request_id,
                    idempotency_key=data.idempotency_key,
                    request_digest=request_digest,
                    agent_version_id=data.agent_version_internal_id,
                    input_document=data.input,
                    locale=data.locale,
                )
                stored = await self._stored(session, run)
                await session.commit()
                return stored, created
            except Exception:
                await session.rollback()
                raise

    async def set_durable_execution_id(
        self,
        *,
        scope: RequestScope,
        run_id: UUID,
        durable_execution_id: str,
    ) -> None:
        workspace_id, project_id = scope.tenant_ids()
        async with self.session_factory() as session:
            run = await session.scalar(
                select(Run)
                .where(
                    Run.id == run_id,
                    Run.workspace_id == workspace_id,
                    Run.project_id == project_id,
                )
                .with_for_update()
            )
            if run is None:
                raise RuntimeError("run_not_found")
            run.durable_execution_id = durable_execution_id
            await session.commit()

    async def get_run(
        self,
        *,
        scope: RequestScope,
        run_id: UUID,
    ) -> StoredRun | None:
        workspace_id, project_id = scope.tenant_ids()
        async with self.session_factory() as session:
            run = await session.scalar(
                select(Run).where(
                    Run.id == run_id,
                    Run.workspace_id == workspace_id,
                    Run.project_id == project_id,
                )
            )
            return None if run is None else await self._stored(session, run)

    async def request_cancel(
        self,
        *,
        scope: RequestScope,
        run_id: UUID,
    ) -> StoredRun | None:
        workspace_id, project_id = scope.tenant_ids()
        async with self.session_factory() as session:
            run = await session.scalar(
                select(Run)
                .where(
                    Run.id == run_id,
                    Run.workspace_id == workspace_id,
                    Run.project_id == project_id,
                )
                .with_for_update()
            )
            if run is None:
                return None
            run.cancel_requested = True
            stored = await self._stored(session, run)
            await session.commit()
            return stored

    async def list_events(
        self,
        *,
        scope: RequestScope,
        run_id: UUID,
        after_sequence: int,
    ) -> list[dict[str, Any]]:
        async with self.session_factory() as session:
            records = await RunRepository(session, scope).list_events(
                run_id,
                after_sequence=after_sequence,
            )
            return [record.document for record in records]

    async def get_trace(
        self,
        *,
        scope: RequestScope,
        run_id: UUID,
    ) -> dict[str, Any] | None:
        workspace_id, project_id = scope.tenant_ids()
        async with self.session_factory() as session:
            trace = await session.scalar(
                select(RunTraceRecord).where(
                    RunTraceRecord.run_id == run_id,
                    RunTraceRecord.workspace_id == workspace_id,
                    RunTraceRecord.project_id == project_id,
                )
            )
            return None if trace is None else trace.document

    async def finalize_start_failure(
        self,
        *,
        scope: RequestScope,
        run: StoredRun,
        error_code: str,
    ) -> None:
        now = datetime.now(UTC)
        started = RunEvent(
            event_id=uuid5(run.id, "event:1:run.started:"),
            run_id=run.id,
            sequence=1,
            type="run.started",
            occurred_at=now,
            correlation_id=run.request_id,
            causation_id=run.request_id,
            node_id=None,
            redaction_policy_id="default-redaction",
            payload={"agent_version_id": run.agent_version_id},
        )
        failed = RunEvent(
            event_id=uuid5(run.id, "event:2:run.failed:"),
            run_id=run.id,
            sequence=2,
            type="run.failed",
            occurred_at=now + timedelta(milliseconds=1),
            correlation_id=run.request_id,
            causation_id=started.event_id,
            node_id=None,
            redaction_policy_id="default-redaction",
            payload={"code": error_code},
        )
        trace = {
            "schema_version": "0.1.0",
            "run_id": str(run.id),
            "request_id": str(run.request_id),
            "agent_version_id": run.agent_version_id,
            "agent_version_digest": run.agent_version_digest,
            "status": "failed",
            "started_at": started.to_document()["occurred_at"],
            "completed_at": failed.to_document()["occurred_at"],
            "input": run.input,
            "output": {},
            "events": [started.to_document(), failed.to_document()],
            "node_executions": [],
            "provenance": {
                "model_resolutions": [],
                "tool_resolutions": [],
                "redaction_policy_id": "default-redaction",
            },
            "metrics": {
                "duration_ms": 1,
                "input_tokens": 0,
                "output_tokens": 0,
                "tool_calls": 0,
                "cost": {"amount": 0, "currency": "USD"},
            },
        }
        async with self.session_factory() as session:
            repository = RunRepository(session, scope)
            try:
                await repository.append_event(run.id, started.to_document())
                await repository.append_event(run.id, failed.to_document())
                await repository.finalize_trace(run.id, trace)
                await WebhookRepository(
                    session,
                    scope,
                ).enqueue_terminal(run_id=run.id, trace=trace)
                await session.commit()
            except Exception:
                await session.rollback()
                raise


class RunService:
    def __init__(
        self,
        *,
        run_persistence: RunPersistence,
        agent_persistence: AgentVersionPersistence,
        durable_execution: DurableExecutionPort,
    ) -> None:
        self.run_persistence = run_persistence
        self.agent_persistence = agent_persistence
        self.durable_execution = durable_execution

    async def create_run(
        self,
        request: CreateRunRequest,
        scope: RequestScope,
    ) -> CreateRunView:
        version = await self.agent_persistence.get_active_version(
            scope=scope,
            version_id=request.agent_version_id,
        )
        if version is None:
            raise ApiError(409, "agent_version_not_active")
        return await self.create_resolved_run(request, scope, version)

    async def create_resolved_run(
        self,
        request: CreateRunRequest,
        scope: RequestScope,
        version: StoredAgentVersion,
    ) -> CreateRunView:
        if version.public_id != request.agent_version_id:
            raise ApiError(409, "agent_version_not_found")
        if version.digest != request.agent_version_digest:
            raise ApiError(409, "agent_version_digest_mismatch")
        input_validation = validate_agent_input(
            version.agent_spec,
            request.input,
        )
        if not input_validation.valid:
            raise ApiError(
                422,
                "run_input_invalid",
                details={
                    "issues": [
                        {
                            "code": issue.code,
                            "json_pointer": issue.json_pointer,
                            "message_key": issue.message_key,
                        }
                        for issue in input_validation.issues
                    ]
                },
            )

        request_digest = content_digest(request.model_dump(mode="json"))
        data = RunCreateData(
            request_id=request.request_id,
            agent_version_internal_id=version.id,
            agent_version_id=version.public_id,
            agent_version_digest=version.digest,
            idempotency_key=request.idempotency_key,
            input=request.input,
            locale=request.locale,
        )
        try:
            run, created = await self.run_persistence.create_idempotent(
                scope=scope,
                data=data,
                request_digest=request_digest,
            )
        except IdempotencyConflict as error:
            raise ApiError(409, "idempotency_key_reused") from error

        if (
            run.status == "queued"
            and run.durable_execution_id is None
        ):
            command = self._command(run, version)
            try:
                durable_id = await self.durable_execution.start_run(command)
            except Exception as error:
                await self.run_persistence.finalize_start_failure(
                    scope=scope,
                    run=run,
                    error_code="durable_execution_unavailable",
                )
                raise ApiError(
                    503,
                    "durable_execution_unavailable",
                    retryable=True,
                ) from error
            try:
                await self.run_persistence.set_durable_execution_id(
                    scope=scope,
                    run_id=run.id,
                    durable_execution_id=durable_id,
                )
            except Exception as error:
                # Temporal workflow IDs are deterministic and USE_EXISTING is
                # configured. A client retry can therefore repair this
                # post-start persistence window without duplicating work.
                raise ApiError(
                    503,
                    "durable_execution_unavailable",
                    retryable=True,
                ) from error

        return CreateRunView(
            run_id=run.id,
            request_id=run.request_id,
            status=run.status,
            reused=not created,
        )

    @staticmethod
    def _command(
        run: StoredRun,
        version: StoredAgentVersion,
    ) -> ExecutionCommand:
        return ExecutionCommand(
            run_id=run.id,
            request_id=run.request_id,
            workspace_id=run.workspace_id,
            project_id=run.project_id,
            agent_version_id=run.agent_version_id,
            agent_version_digest=run.agent_version_digest,
            agent_spec=version.agent_spec,
            input=run.input,
            locale=run.locale,
        )

    async def get_run(self, run_id: UUID, scope: RequestScope) -> RunView:
        run = await self.run_persistence.get_run(scope=scope, run_id=run_id)
        if run is None:
            raise ApiError(404, "run_not_found")
        return RunView(
            run_id=run.id,
            request_id=run.request_id,
            agent_version_id=run.agent_version_id,
            agent_version_digest=run.agent_version_digest,
            status=run.status,
            locale=run.locale,
            input=run.input,
            output=run.output,
            durable_execution_id=run.durable_execution_id,
            cancel_requested=run.cancel_requested,
        )

    async def cancel_run(
        self,
        run_id: UUID,
        scope: RequestScope,
    ) -> CancelRunView:
        run = await self.run_persistence.request_cancel(
            scope=scope,
            run_id=run_id,
        )
        if run is None:
            raise ApiError(404, "run_not_found")
        if run.status in TERMINAL_STATUSES:
            return CancelRunView(run_id=run_id, status="already_terminal")
        status = await self.durable_execution.request_cancel(run_id)
        return CancelRunView(run_id=run_id, status=status)

    async def list_events(
        self,
        run_id: UUID,
        scope: RequestScope,
        *,
        after_sequence: int,
    ) -> list[dict[str, Any]]:
        if await self.run_persistence.get_run(scope=scope, run_id=run_id) is None:
            raise ApiError(404, "run_not_found")
        return await self.run_persistence.list_events(
            scope=scope,
            run_id=run_id,
            after_sequence=after_sequence,
        )

    async def get_trace(
        self,
        run_id: UUID,
        scope: RequestScope,
    ) -> dict[str, Any]:
        run = await self.run_persistence.get_run(scope=scope, run_id=run_id)
        if run is None:
            raise ApiError(404, "run_not_found")
        trace = await self.run_persistence.get_trace(
            scope=scope,
            run_id=run_id,
        )
        if trace is None:
            if run.status not in TERMINAL_STATUSES:
                raise ApiError(409, "run_not_terminal")
            raise ApiError(503, "run_trace_unavailable", retryable=True)
        return trace
