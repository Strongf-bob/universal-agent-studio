import copy
import json
from importlib.util import find_spec
from pathlib import Path
from typing import Any, cast
from uuid import UUID

import pytest
from sqlalchemy.ext.asyncio import AsyncSession
from universal_agent_kernel.contracts.canonical import content_digest
from universal_agent_platform_store.models import Base
from universal_agent_platform_store.repositories.agents import AgentRepository
from universal_agent_platform_store.repositories.drafts import (
    DraftRepository,
    DraftRevisionConflict,
)
from universal_agent_platform_store.scope import RequestScope

ROOT = Path(__file__).parents[2]
GOLDEN_AGENT = (
    ROOT
    / "contracts"
    / "examples"
    / "v0.1.0"
    / "valid"
    / "agent.calculator.ru-en.json"
)


def agent_spec() -> dict[str, Any]:
    return cast(
        dict[str, Any],
        json.loads(GOLDEN_AGENT.read_text(encoding="utf-8")),
    )


def draft_layout() -> dict[str, Any]:
    return {
        "nodes": [
            {
                "node_id": "user-input",
                "x": 0,
                "y": 80,
            }
        ],
        "viewport": {"x": 0, "y": 0, "zoom": 1},
    }


async def activate_golden(
    session: AsyncSession,
    scope: RequestScope,
) -> None:
    repository = AgentRepository(session, scope)
    spec = agent_spec()
    version, _ = await repository.import_version(
        spec,
        content_digest(spec),
    )
    await repository.activate(
        agent_key=spec["agent_id"],
        version_id=version.id,
        expected_previous_version_id=None,
    )
    await session.commit()


def test_agent_draft_table_is_part_of_platform_metadata() -> None:
    assert "agent_drafts" in Base.metadata.tables


def test_scoped_draft_repository_module_is_available() -> None:
    assert (
        find_spec(
            "universal_agent_platform_store.repositories.drafts"
        )
        is not None
    )


@pytest.mark.asyncio
async def test_create_from_active_is_idempotent(
    database_session: AsyncSession,
    request_scope: RequestScope,
) -> None:
    await activate_golden(database_session, request_scope)
    repository = DraftRepository(database_session, request_scope)

    first, first_created = await repository.create_from_active(
        "calculator-agent",
        draft_layout(),
    )
    second, second_created = await repository.create_from_active(
        "calculator-agent",
        {"nodes": [], "viewport": {"x": 20, "y": 0, "zoom": 1}},
    )

    assert first_created is True
    assert second_created is False
    assert second.id == first.id
    assert second.revision == 1
    assert second.layout == draft_layout()


@pytest.mark.asyncio
async def test_update_uses_expected_revision(
    database_session: AsyncSession,
    request_scope: RequestScope,
) -> None:
    await activate_golden(database_session, request_scope)
    repository = DraftRepository(database_session, request_scope)
    await repository.create_from_active(
        "calculator-agent",
        draft_layout(),
    )
    changed = copy.deepcopy(agent_spec())
    changed["localized_metadata"]["name"]["en-US"] = "Math Agent"

    updated = await repository.update(
        "calculator-agent",
        expected_revision=1,
        agent_spec=changed,
        digest=content_digest(changed),
        layout=draft_layout(),
    )

    assert updated.revision == 2
    assert updated.digest == content_digest(changed)
    with pytest.raises(DraftRevisionConflict):
        await repository.update(
            "calculator-agent",
            expected_revision=1,
            agent_spec=changed,
            digest=content_digest(changed),
            layout=draft_layout(),
        )


@pytest.mark.asyncio
async def test_foreign_project_cannot_read_draft(
    database_session: AsyncSession,
    request_scope: RequestScope,
) -> None:
    await activate_golden(database_session, request_scope)
    repository = DraftRepository(database_session, request_scope)
    await repository.create_from_active(
        "calculator-agent",
        draft_layout(),
    )
    foreign_scope = RequestScope(
        workspace_id=request_scope.workspace_id,
        project_id=UUID("dddddddd-dddd-4ddd-8ddd-dddddddddddd"),
        owner_id=request_scope.owner_id,
    )

    assert (
        await DraftRepository(database_session, foreign_scope).get(
            "calculator-agent"
        )
        is None
    )
