"""Idempotent event, trace and calculator persistence adapters."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Protocol, cast
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from universal_agent_kernel.domain import RunEvent, RunTrace
from universal_agent_kernel.ports import RunEventSink, ToolGatewayPort, TraceStore
from universal_agent_kernel.tools.calculator import CalculatorTool
from universal_agent_platform_store.models import ToolInvocation
from universal_agent_platform_store.repositories.runs import RunRepository
from universal_agent_platform_store.repositories.webhooks import WebhookRepository
from universal_agent_platform_store.scope import RequestScope


class RuntimePersistence(Protocol):
    async def append_event(
        self,
        *,
        scope: RequestScope,
        run_id: UUID,
        document: dict[str, Any],
    ) -> None: ...

    async def list_events(
        self,
        *,
        scope: RequestScope,
        run_id: UUID,
    ) -> list[dict[str, Any]]: ...

    async def finalize_trace(
        self,
        *,
        scope: RequestScope,
        run_id: UUID,
        document: dict[str, Any],
    ) -> None: ...

    async def invoke_calculator_once(
        self,
        *,
        scope: RequestScope,
        run_id: UUID,
        node_id: str,
        invocation_key: str,
        tool_id: str,
        arguments: Mapping[str, object],
    ) -> Mapping[str, object]: ...


class SqlRuntimePersistence:
    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
    ) -> None:
        self.session_factory = session_factory

    async def append_event(
        self,
        *,
        scope: RequestScope,
        run_id: UUID,
        document: dict[str, Any],
    ) -> None:
        async with self.session_factory() as session:
            try:
                await RunRepository(session, scope).append_event(run_id, document)
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    async def list_events(
        self,
        *,
        scope: RequestScope,
        run_id: UUID,
    ) -> list[dict[str, Any]]:
        async with self.session_factory() as session:
            records = await RunRepository(session, scope).list_events(run_id)
            return [record.document for record in records]

    async def finalize_trace(
        self,
        *,
        scope: RequestScope,
        run_id: UUID,
        document: dict[str, Any],
    ) -> None:
        async with self.session_factory() as session:
            try:
                await RunRepository(session, scope).finalize_trace(run_id, document)
                await WebhookRepository(session, scope).enqueue_terminal(
                    run_id=run_id,
                    trace=document,
                )
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    async def invoke_calculator_once(
        self,
        *,
        scope: RequestScope,
        run_id: UUID,
        node_id: str,
        invocation_key: str,
        tool_id: str,
        arguments: Mapping[str, object],
    ) -> Mapping[str, object]:
        workspace_id, project_id = scope.tenant_ids()
        lock_key = f"{workspace_id}:{project_id}:{run_id}:{node_id}:{invocation_key}"
        async with self.session_factory() as session:
            try:
                await session.scalar(
                    select(
                        func.pg_advisory_xact_lock(func.hashtextextended(lock_key, 0))
                    )
                )
                existing = await session.scalar(
                    select(ToolInvocation).where(
                        ToolInvocation.workspace_id == workspace_id,
                        ToolInvocation.project_id == project_id,
                        ToolInvocation.run_id == run_id,
                        ToolInvocation.node_id == node_id,
                        ToolInvocation.logical_invocation_key == invocation_key,
                    )
                )
                if existing is not None and existing.result_document is not None:
                    return cast(Mapping[str, object], existing.result_document)

                result = await CalculatorTool().invoke(tool_id, arguments)
                record = existing or ToolInvocation(
                    workspace_id=workspace_id,
                    project_id=project_id,
                    run_id=run_id,
                    node_id=node_id,
                    logical_invocation_key=invocation_key,
                    status="completed",
                )
                record.status = "completed"
                record.result_document = dict(result)
                if existing is None:
                    session.add(record)
                await session.commit()
                return result
            except Exception:
                await session.rollback()
                raise


class PersistedEventSink(RunEventSink):
    def __init__(
        self,
        persistence: RuntimePersistence,
        scope: RequestScope,
        run_id: UUID,
    ) -> None:
        self.persistence = persistence
        self.scope = scope
        self.run_id = run_id

    async def append(self, event: RunEvent) -> None:
        await self.persistence.append_event(
            scope=self.scope,
            run_id=self.run_id,
            document=event.to_document(),
        )


class PersistedTraceStore(TraceStore):
    def __init__(
        self,
        persistence: RuntimePersistence,
        scope: RequestScope,
        run_id: UUID,
    ) -> None:
        self.persistence = persistence
        self.scope = scope
        self.run_id = run_id

    async def save(self, trace: RunTrace) -> None:
        await self.persistence.finalize_trace(
            scope=self.scope,
            run_id=self.run_id,
            document=trace.to_document(),
        )


class IdempotentCalculatorGateway(ToolGatewayPort):
    def __init__(
        self,
        persistence: RuntimePersistence,
        scope: RequestScope,
        run_id: UUID,
        node_id: str,
    ) -> None:
        self.persistence = persistence
        self.scope = scope
        self.run_id = run_id
        self.node_id = node_id

    async def invoke(
        self,
        tool_id: str,
        arguments: Mapping[str, object],
    ) -> Mapping[str, object]:
        return await self.persistence.invoke_calculator_once(
            scope=self.scope,
            run_id=self.run_id,
            node_id=self.node_id,
            invocation_key=f"{self.run_id}:{self.node_id}:1",
            tool_id=tool_id,
            arguments=arguments,
        )
