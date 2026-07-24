"""Scoped idempotent run, event and terminal trace persistence."""

from __future__ import annotations

import hashlib
from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from universal_agent_platform_store.models import (
    Run,
    RunEventRecord,
    RunRequest,
    RunTraceRecord,
    utc_now,
)
from universal_agent_platform_store.repositories.base import ScopedRepository
from universal_agent_platform_store.scope import RequestScope


class IdempotencyConflict(RuntimeError):
    pass


class EventConflict(RuntimeError):
    pass


class TerminalTraceConflict(RuntimeError):
    pass


def _parse_timestamp(value: object) -> datetime:
    if not isinstance(value, str):
        return utc_now()
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


class RunRepository(ScopedRepository):
    def __init__(
        self,
        session: AsyncSession,
        scope: RequestScope | None,
    ) -> None:
        super().__init__(session, scope)
        self.workspace_id, self.project_id = self.scope.tenant_ids()

    async def create_idempotent(
        self,
        *,
        request_id: UUID,
        idempotency_key: str,
        request_digest: str,
        agent_version_id: UUID,
        input_document: dict[str, Any],
        locale: str,
    ) -> tuple[Run, bool]:
        lock_material = (
            f"{self.workspace_id}:{self.project_id}:{idempotency_key}"
        ).encode()
        lock_key = int.from_bytes(
            hashlib.sha256(lock_material).digest()[:8],
            byteorder="big",
            signed=True,
        )
        await self.session.execute(
            text("SELECT pg_advisory_xact_lock(:lock_key)"),
            {"lock_key": lock_key},
        )
        existing_request = await self.session.scalar(
            select(RunRequest).where(
                RunRequest.workspace_id == self.workspace_id,
                RunRequest.project_id == self.project_id,
                RunRequest.idempotency_key == idempotency_key,
            )
        )
        if existing_request is not None:
            if existing_request.request_digest != request_digest:
                raise IdempotencyConflict("idempotency_key_reused")
            existing_run = await self.session.scalar(
                select(Run).where(
                    Run.id == existing_request.resolved_run_id,
                    Run.workspace_id == self.workspace_id,
                    Run.project_id == self.project_id,
                )
            )
            if existing_run is None:
                raise RuntimeError("resolved_run_missing")
            return existing_run, False

        run = Run(
            id=uuid4(),
            workspace_id=self.workspace_id,
            project_id=self.project_id,
            agent_version_id=agent_version_id,
            status="queued",
            locale=locale,
            input_document=input_document,
            cancel_requested=False,
        )
        request = RunRequest(
            id=request_id,
            workspace_id=self.workspace_id,
            project_id=self.project_id,
            idempotency_key=idempotency_key,
            request_digest=request_digest,
            request_document={
                "agent_version_id": str(agent_version_id),
                "input": input_document,
                "locale": locale,
            },
            resolved_run_id=run.id,
        )
        self.session.add_all([run, request])
        await self.session.flush()
        return run, True

    async def append_event(
        self,
        run_id: UUID,
        document: dict[str, Any],
    ) -> tuple[RunEventRecord, bool]:
        event_id = UUID(str(document["event_id"]))
        sequence = int(document["sequence"])
        existing = await self.session.scalar(
            select(RunEventRecord).where(
                RunEventRecord.workspace_id == self.workspace_id,
                RunEventRecord.project_id == self.project_id,
                (
                    (RunEventRecord.id == event_id)
                    | (
                        (RunEventRecord.run_id == run_id)
                        & (RunEventRecord.sequence == sequence)
                    )
                ),
            )
        )
        if existing is not None:
            if existing.run_id == run_id and existing.document == document:
                return existing, False
            raise EventConflict("run_event_conflict")

        record = RunEventRecord(
            id=event_id,
            workspace_id=self.workspace_id,
            project_id=self.project_id,
            run_id=run_id,
            sequence=sequence,
            event_type=str(document["type"]),
            node_id=(
                str(document["node_id"])
                if document.get("node_id") is not None
                else None
            ),
            occurred_at=_parse_timestamp(document.get("occurred_at")),
            document=document,
        )
        self.session.add(record)
        if document.get("type") == "run.started":
            run = await self.session.scalar(
                select(Run)
                .where(
                    Run.id == run_id,
                    Run.workspace_id == self.workspace_id,
                    Run.project_id == self.project_id,
                )
                .with_for_update()
            )
            if run is None:
                raise RuntimeError("run_not_found")
            if run.status == "queued":
                run.status = "running"
                run.started_at = record.occurred_at
        await self.session.flush()
        return record, True

    async def finalize_trace(
        self,
        run_id: UUID,
        document: dict[str, Any],
    ) -> tuple[RunTraceRecord, bool]:
        existing = await self.session.scalar(
            select(RunTraceRecord).where(
                RunTraceRecord.workspace_id == self.workspace_id,
                RunTraceRecord.project_id == self.project_id,
                RunTraceRecord.run_id == run_id,
            )
        )
        if existing is not None:
            if existing.document == document:
                return existing, False
            raise TerminalTraceConflict("run_trace_already_finalized")

        run = await self.session.scalar(
            select(Run)
            .where(
                Run.id == run_id,
                Run.workspace_id == self.workspace_id,
                Run.project_id == self.project_id,
            )
            .with_for_update()
        )
        if run is None:
            raise RuntimeError("run_not_found")
        status = str(document["status"])
        output = document.get("output")
        run.status = status
        run.output_document = output if isinstance(output, dict) else {}
        run.completed_at = utc_now()

        trace = RunTraceRecord(
            id=uuid4(),
            workspace_id=self.workspace_id,
            project_id=self.project_id,
            run_id=run.id,
            schema_version=str(document["schema_version"]),
            document=document,
        )
        self.session.add(trace)
        await self.session.flush()
        return trace, True

    async def list_events(
        self,
        run_id: UUID,
        *,
        after_sequence: int = 0,
    ) -> list[RunEventRecord]:
        result = await self.session.scalars(
            select(RunEventRecord)
            .where(
                RunEventRecord.workspace_id == self.workspace_id,
                RunEventRecord.project_id == self.project_id,
                RunEventRecord.run_id == run_id,
                RunEventRecord.sequence > after_sequence,
            )
            .order_by(RunEventRecord.sequence)
        )
        return list(result)
