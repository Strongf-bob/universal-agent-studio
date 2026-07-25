from __future__ import annotations

import asyncio
import json
from pathlib import Path
from uuid import uuid4

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
)
from universal_agent_platform_store.models import AgentVersion
from universal_agent_platform_store.repositories.drafts import DraftRepository
from universal_agent_platform_store.repositories.locks import (
    agent_publication_lock_key,
)
from universal_agent_platform_store.repositories.publishing import (
    PublishingRepository,
)
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


@pytest.mark.asyncio
async def test_legacy_activation_cannot_bypass_publication_ledger(
    database_session: AsyncSession,
    request_scope: RequestScope,
) -> None:
    service = AgentVersionService(
        SqlAgentVersionPersistence.from_session(database_session)
    )
    first = await service.import_raw(GOLDEN_AGENT.read_bytes(), request_scope)
    await service.activate(
        agent_id="calculator-agent",
        version_id=first.version_id,
        expected_previous_version_id=None,
        scope=request_scope,
    )
    draft, _ = await DraftRepository(
        database_session,
        request_scope,
    ).create_from_active(
        "calculator-agent",
        {"nodes": [], "viewport": {"x": 0, "y": 0, "zoom": 1}},
    )
    version = await database_session.scalar(
        select(AgentVersion).where(AgentVersion.digest == first.digest)
    )
    assert version is not None
    await PublishingRepository(
        database_session,
        request_scope,
    ).publish_draft(
        "calculator-agent",
        expected_revision=draft.revision,
        expected_active_version_id=version.id,
    )
    await database_session.commit()
    document = json.loads(GOLDEN_AGENT.read_bytes())
    document["revision"] = 2
    second = await service.import_raw(json.dumps(document).encode(), request_scope)

    with pytest.raises(ApiError) as error:
        await service.activate(
            agent_id="calculator-agent",
            version_id=second.version_id,
            expected_previous_version_id=first.version_id,
            scope=request_scope,
        )

    assert error.value.status_code == 409
    assert error.value.document["code"] == "published_agent_requires_publish"


@pytest.mark.asyncio
async def test_legacy_activation_serializes_with_first_publish(
    database_engine: AsyncEngine,
    database_session: AsyncSession,
    request_scope: RequestScope,
) -> None:
    setup_service = AgentVersionService(
        SqlAgentVersionPersistence.from_session(database_session)
    )
    first = await setup_service.import_raw(
        GOLDEN_AGENT.read_bytes(),
        request_scope,
    )
    await setup_service.activate(
        agent_id="calculator-agent",
        version_id=first.version_id,
        expected_previous_version_id=None,
        scope=request_scope,
    )
    document = json.loads(GOLDEN_AGENT.read_bytes())
    document["revision"] = 2
    second = await setup_service.import_raw(
        json.dumps(document).encode(),
        request_scope,
    )
    draft, _ = await DraftRepository(
        database_session,
        request_scope,
    ).create_from_active(
        "calculator-agent",
        {"nodes": [], "viewport": {"x": 0, "y": 0, "zoom": 1}},
    )
    await database_session.commit()
    workspace_id, project_id = request_scope.tenant_ids()
    lock_key = agent_publication_lock_key(
        workspace_id,
        project_id,
        "calculator-agent",
    )
    await database_session.scalar(
        select(
            func.pg_advisory_xact_lock(
                func.hashtextextended(lock_key, 0)
            )
        )
    )
    concurrent_service = AgentVersionService(
        SqlAgentVersionPersistence.from_factory(
            async_sessionmaker(database_engine, expire_on_commit=False)
        )
    )
    activation = asyncio.create_task(
        concurrent_service.activate(
            agent_id="calculator-agent",
            version_id=second.version_id,
            expected_previous_version_id=first.version_id,
            scope=request_scope,
        )
    )
    await asyncio.sleep(0.05)
    assert not activation.done()
    first_record = await database_session.scalar(
        select(AgentVersion).where(AgentVersion.digest == first.digest)
    )
    assert first_record is not None
    await PublishingRepository(
        database_session,
        request_scope,
    ).publish_draft(
        "calculator-agent",
        expected_revision=draft.revision,
        expected_active_version_id=first_record.id,
    )
    await database_session.commit()

    with pytest.raises(ApiError) as error:
        await activation

    assert error.value.status_code == 409
    assert error.value.document["code"] == "published_agent_requires_publish"
