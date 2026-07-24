from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any, cast
from uuid import UUID, uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession
from universal_agent_kernel.contracts.canonical import content_digest
from universal_agent_platform_store.repositories.agents import AgentRepository
from universal_agent_platform_store.repositories.runs import (
    IdempotencyConflict,
    RunRepository,
    TerminalTraceConflict,
)
from universal_agent_platform_store.scope import RequestScope

ROOT = Path(__file__).parents[2]
GOLDEN_AGENT = (
    ROOT / "contracts" / "examples" / "v0.1.0" / "valid" / "agent.calculator.ru-en.json"
)


def agent_spec() -> dict[str, Any]:
    return cast(dict[str, Any], json.loads(GOLDEN_AGENT.read_text(encoding="utf-8")))


async def version_id(
    session: AsyncSession,
    scope: RequestScope,
) -> UUID:
    spec = agent_spec()
    version, _ = await AgentRepository(session, scope).import_version(
        spec,
        content_digest(spec),
    )
    return version.id


@pytest.mark.asyncio
async def test_idempotency_same_body_reuses_run(
    database_session: AsyncSession,
    request_scope: RequestScope,
) -> None:
    repository = RunRepository(database_session, request_scope)
    agent_version_id = await version_id(database_session, request_scope)

    first, first_created = await repository.create_idempotent(
        request_id=uuid4(),
        idempotency_key="local-test-idempotency-0001",
        request_digest="1" * 64,
        agent_version_id=agent_version_id,
        input_document={"question": "19 * 23"},
        locale="en-US",
    )
    second, second_created = await repository.create_idempotent(
        request_id=uuid4(),
        idempotency_key="local-test-idempotency-0001",
        request_digest="1" * 64,
        agent_version_id=agent_version_id,
        input_document={"question": "19 * 23"},
        locale="en-US",
    )

    assert first_created is True
    assert second_created is False
    assert second.id == first.id


@pytest.mark.asyncio
async def test_idempotency_different_body_conflicts(
    database_session: AsyncSession,
    request_scope: RequestScope,
) -> None:
    repository = RunRepository(database_session, request_scope)
    agent_version_id = await version_id(database_session, request_scope)
    await repository.create_idempotent(
        request_id=uuid4(),
        idempotency_key="local-test-idempotency-0002",
        request_digest="1" * 64,
        agent_version_id=agent_version_id,
        input_document={"question": "first"},
        locale="en-US",
    )

    with pytest.raises(IdempotencyConflict):
        await repository.create_idempotent(
            request_id=uuid4(),
            idempotency_key="local-test-idempotency-0002",
            request_digest="2" * 64,
            agent_version_id=agent_version_id,
            input_document={"question": "second"},
            locale="en-US",
        )


@pytest.mark.asyncio
async def test_concurrent_identical_requests_reuse_one_run(
    database_engine: AsyncEngine,
    database_session: AsyncSession,
    request_scope: RequestScope,
) -> None:
    agent_version_id = await version_id(database_session, request_scope)
    await database_session.commit()

    async def create() -> tuple[UUID, bool]:
        async with AsyncSession(
            database_engine,
            expire_on_commit=False,
        ) as session:
            run, created = await RunRepository(
                session,
                request_scope,
            ).create_idempotent(
                request_id=uuid4(),
                idempotency_key="local-concurrent-idempotency-0001",
                request_digest="9" * 64,
                agent_version_id=agent_version_id,
                input_document={"question": "19 * 23"},
                locale="en-US",
            )
            await session.commit()
            return run.id, created

    first, second = await asyncio.gather(create(), create())

    assert first[0] == second[0]
    assert sorted([first[1], second[1]]) == [False, True]


@pytest.mark.asyncio
async def test_duplicate_event_retry_returns_existing_event(
    database_session: AsyncSession,
    request_scope: RequestScope,
) -> None:
    repository = RunRepository(database_session, request_scope)
    agent_version_id = await version_id(database_session, request_scope)
    run, _ = await repository.create_idempotent(
        request_id=uuid4(),
        idempotency_key="local-test-idempotency-0003",
        request_digest="3" * 64,
        agent_version_id=agent_version_id,
        input_document={"question": "event"},
        locale="en-US",
    )
    event_id = uuid4()
    document = {
        "schema_version": "0.1.0",
        "event_id": str(event_id),
        "run_id": str(run.id),
        "sequence": 1,
        "type": "run.started",
    }

    first, first_created = await repository.append_event(run.id, document)
    second, second_created = await repository.append_event(run.id, document)
    await database_session.refresh(run)

    assert first_created is True
    assert second_created is False
    assert second.id == first.id
    assert run.status == "running"
    assert run.started_at is not None


@pytest.mark.asyncio
async def test_terminal_trace_finalizes_once(
    database_session: AsyncSession,
    request_scope: RequestScope,
) -> None:
    repository = RunRepository(database_session, request_scope)
    agent_version_id = await version_id(database_session, request_scope)
    run, _ = await repository.create_idempotent(
        request_id=uuid4(),
        idempotency_key="local-test-idempotency-0004",
        request_digest="4" * 64,
        agent_version_id=agent_version_id,
        input_document={"question": "trace"},
        locale="en-US",
    )
    trace = {
        "schema_version": "0.1.0",
        "run_id": str(run.id),
        "status": "completed",
        "output": {"value": 437},
    }

    first, first_created = await repository.finalize_trace(run.id, trace)
    second, second_created = await repository.finalize_trace(run.id, trace)
    with pytest.raises(TerminalTraceConflict):
        await repository.finalize_trace(
            run.id,
            {**trace, "output": {"value": 438}},
        )

    assert first_created is True
    assert second_created is False
    assert second.id == first.id
