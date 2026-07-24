from __future__ import annotations

import json
from pathlib import Path
from typing import Any, cast

import pytest
from sqlalchemy.ext.asyncio import AsyncSession
from universal_agent_kernel.contracts.canonical import content_digest
from universal_agent_platform_store.repositories.agents import (
    ActiveVersionConflict,
    AgentRepository,
)
from universal_agent_platform_store.scope import RequestScope

ROOT = Path(__file__).parents[2]
GOLDEN_AGENT = (
    ROOT / "contracts" / "examples" / "v0.1.0" / "valid" / "agent.calculator.ru-en.json"
)


def agent_spec() -> dict[str, Any]:
    return cast(dict[str, Any], json.loads(GOLDEN_AGENT.read_text(encoding="utf-8")))


@pytest.mark.asyncio
async def test_identical_agent_digest_reuses_immutable_version(
    database_session: AsyncSession,
    request_scope: RequestScope,
) -> None:
    repository = AgentRepository(database_session, request_scope)
    spec = agent_spec()
    digest = content_digest(spec)

    first, first_created = await repository.import_version(spec, digest)
    second, second_created = await repository.import_version(spec, digest)
    await database_session.commit()

    assert first_created is True
    assert second_created is False
    assert second.id == first.id
    assert second.agent_spec == first.agent_spec


@pytest.mark.asyncio
async def test_active_pointer_uses_expected_previous_version(
    database_session: AsyncSession,
    request_scope: RequestScope,
) -> None:
    repository = AgentRepository(database_session, request_scope)
    spec = agent_spec()
    first, _ = await repository.import_version(spec, content_digest(spec))
    await repository.activate(
        agent_key=spec["agent_id"],
        version_id=first.id,
        expected_previous_version_id=None,
    )

    changed = dict(spec)
    changed["revision"] = 2
    second, _ = await repository.import_version(changed, content_digest(changed))
    with pytest.raises(ActiveVersionConflict):
        await repository.activate(
            agent_key=spec["agent_id"],
            version_id=second.id,
            expected_previous_version_id=None,
        )

    active = await repository.activate(
        agent_key=spec["agent_id"],
        version_id=second.id,
        expected_previous_version_id=first.id,
    )
    await database_session.commit()

    assert active.version_id == second.id
