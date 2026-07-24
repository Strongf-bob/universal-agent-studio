from __future__ import annotations

import json
from pathlib import Path
from typing import Any, cast
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession
from universal_agent_kernel.contracts.canonical import content_digest
from universal_agent_platform_store.models import Project, Workspace
from universal_agent_platform_store.repositories.agents import AgentRepository
from universal_agent_platform_store.scope import RequestScope

ROOT = Path(__file__).parents[2]
GOLDEN_AGENT = (
    ROOT / "contracts" / "examples" / "v0.1.0" / "valid" / "agent.calculator.ru-en.json"
)


@pytest.mark.asyncio
async def test_agent_versions_cannot_be_read_or_activated_across_projects(
    database_session: AsyncSession,
    request_scope: RequestScope,
) -> None:
    spec = cast(dict[str, Any], json.loads(GOLDEN_AGENT.read_text(encoding="utf-8")))
    owner_repository = AgentRepository(database_session, request_scope)
    version, _ = await owner_repository.import_version(spec, content_digest(spec))

    foreign_workspace = Workspace(
        id=uuid4(),
        slug=f"foreign-{uuid4().hex[:8]}",
        name="Foreign workspace",
    )
    database_session.add(foreign_workspace)
    await database_session.flush()
    foreign_project = Project(
        id=uuid4(),
        workspace_id=foreign_workspace.id,
        slug="foreign",
        name="Foreign project",
    )
    database_session.add(foreign_project)
    await database_session.flush()
    foreign_scope = RequestScope(
        workspace_id=foreign_workspace.id,
        project_id=foreign_project.id,
    )
    foreign_repository = AgentRepository(database_session, foreign_scope)

    assert await foreign_repository.get_version(version.id) is None
    assert (
        await foreign_repository.get_version_by_public_id("calculator-agent-v1")
        is None
    )
    assert await foreign_repository.get_active_version("calculator-agent") is None
