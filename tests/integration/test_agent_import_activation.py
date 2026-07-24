from __future__ import annotations

import json
from pathlib import Path
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession
from universal_agent_platform_store.scope import RequestScope
from universal_agent_studio_api.agents.service import (
    AgentVersionService,
    SqlAgentVersionPersistence,
)
from universal_agent_studio_api.errors import ApiError

ROOT = Path(__file__).parents[2]
GOLDEN_AGENT = (
    ROOT / "contracts" / "examples" / "v0.1.0" / "valid" / "agent.calculator.ru-en.json"
)


@pytest.mark.asyncio
async def test_agent_version_reads_are_project_scoped(
    database_session: AsyncSession,
    request_scope: RequestScope,
) -> None:
    service = AgentVersionService(
        SqlAgentVersionPersistence.from_session(database_session)
    )
    imported = await service.import_raw(GOLDEN_AGENT.read_bytes(), request_scope)
    other_project_scope = RequestScope(
        workspace_id=request_scope.workspace_id,
        project_id=uuid4(),
        owner_id=request_scope.owner_id,
    )

    with pytest.raises(ApiError) as error:
        await service.get_version(
            imported.version_id,
            other_project_scope,
        )

    assert error.value.status_code == 404
    assert error.value.document["code"] == "agent_version_not_found"


@pytest.mark.asyncio
async def test_import_and_activation_commit_atomically(
    database_session: AsyncSession,
    request_scope: RequestScope,
) -> None:
    service = AgentVersionService(
        SqlAgentVersionPersistence.from_session(database_session)
    )
    document = json.loads(GOLDEN_AGENT.read_bytes())
    first = await service.import_raw(GOLDEN_AGENT.read_bytes(), request_scope)
    document["revision"] = 2
    second = await service.import_raw(
        json.dumps(document).encode(),
        request_scope,
    )

    active = await service.activate(
        agent_id="calculator-agent",
        version_id=first.version_id,
        expected_previous_version_id=None,
        scope=request_scope,
    )
    changed = await service.activate(
        agent_id="calculator-agent",
        version_id=second.version_id,
        expected_previous_version_id=first.version_id,
        scope=request_scope,
    )

    assert active.active_version_id == first.version_id
    assert changed.active_version_id == second.version_id
