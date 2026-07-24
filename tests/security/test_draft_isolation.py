from __future__ import annotations

import json
from pathlib import Path
from typing import Any, cast
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession
from universal_agent_kernel.contracts.canonical import content_digest
from universal_agent_platform_store.models import Project
from universal_agent_platform_store.repositories.agents import AgentRepository
from universal_agent_platform_store.repositories.drafts import (
    DraftNotFound,
    DraftRepository,
)
from universal_agent_platform_store.scope import RequestScope

ROOT = Path(__file__).parents[2]
GOLDEN_AGENT = (
    ROOT / "contracts" / "examples" / "v0.1.0" / "valid" / "agent.calculator.ru-en.json"
)


@pytest.mark.asyncio
async def test_foreign_project_cannot_read_or_update_agent_draft(
    database_session: AsyncSession,
    request_scope: RequestScope,
) -> None:
    spec = cast(
        dict[str, Any],
        json.loads(GOLDEN_AGENT.read_text(encoding="utf-8")),
    )
    agents = AgentRepository(database_session, request_scope)
    version, _ = await agents.import_version(spec, content_digest(spec))
    await agents.activate(
        agent_key="calculator-agent",
        version_id=version.id,
        expected_previous_version_id=None,
    )
    owner_drafts = DraftRepository(database_session, request_scope)
    owner_draft, _ = await owner_drafts.create_from_active(
        "calculator-agent",
        {
            "nodes": [{"node_id": "user-input", "x": 0, "y": 80}],
            "viewport": {"x": 0, "y": 0, "zoom": 1},
        },
    )

    foreign_project = Project(
        id=uuid4(),
        workspace_id=request_scope.workspace_id,
        slug=f"foreign-{uuid4().hex[:8]}",
        name="Foreign project",
    )
    database_session.add(foreign_project)
    await database_session.flush()
    foreign_scope = RequestScope(
        workspace_id=request_scope.workspace_id,
        project_id=foreign_project.id,
        owner_id=request_scope.owner_id,
    )
    foreign_drafts = DraftRepository(database_session, foreign_scope)

    assert await foreign_drafts.get("calculator-agent") is None
    with pytest.raises(DraftNotFound):
        await foreign_drafts.update(
            "calculator-agent",
            expected_revision=owner_draft.revision,
            agent_spec=spec,
            digest=content_digest(spec),
            layout=owner_draft.layout,
        )
    persisted = await owner_drafts.get("calculator-agent")
    assert persisted is not None
    assert persisted.revision == owner_draft.revision
