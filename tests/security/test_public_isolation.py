from __future__ import annotations

import json
from pathlib import Path
from typing import Any, cast
from uuid import UUID, uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker
from universal_agent_kernel.contracts.canonical import content_digest
from universal_agent_kernel.contracts.generated import (
    ApiKeyCreateRequest,
    ApiKeyScope,
    PublicRunCreateRequest,
)
from universal_agent_platform_store.repositories.agents import AgentRepository
from universal_agent_platform_store.repositories.drafts import DraftRepository
from universal_agent_platform_store.repositories.publishing import (
    PublishingRepository,
)
from universal_agent_platform_store.scope import RequestScope
from universal_agent_studio_api.errors import ApiError
from universal_agent_studio_api.publishing.public_service import PublicService
from universal_agent_studio_api.publishing.service import PublishingService
from universal_agent_studio_api.runs.service import (
    CreateRunRequest,
    CreateRunView,
    RunView,
)

ROOT = Path(__file__).parents[2]
GOLDEN = (
    ROOT
    / "contracts"
    / "examples"
    / "v0.1.0"
    / "valid"
    / "agent.calculator.ru-en.json"
)


class FakeRunService:
    def __init__(self) -> None:
        self.runs: dict[UUID, RunView] = {}

    async def create_resolved_run(
        self,
        request: CreateRunRequest,
        scope: RequestScope,
        version: object,
    ) -> CreateRunView:
        del scope, version
        run_id = uuid4()
        self.runs[run_id] = RunView(
            run_id=run_id,
            request_id=request.request_id,
            agent_version_id=request.agent_version_id,
            agent_version_digest=request.agent_version_digest,
            status="queued",
            locale=request.locale,
            input=request.input,
            output=None,
            durable_execution_id="must-not-leak",
            cancel_requested=False,
        )
        return CreateRunView(
            run_id=run_id,
            request_id=request.request_id,
            status="queued",
            reused=False,
        )

    async def get_run(self, run_id: UUID, scope: RequestScope) -> RunView:
        del scope
        return self.runs[run_id]

    async def list_events(
        self,
        run_id: UUID,
        scope: RequestScope,
        *,
        after_sequence: int,
    ) -> list[dict[str, Any]]:
        del run_id, scope, after_sequence
        return []


async def _publish(
    session: AsyncSession,
    scope: RequestScope,
) -> None:
    spec = cast(dict[str, Any], json.loads(GOLDEN.read_text(encoding="utf-8")))
    agents = AgentRepository(session, scope)
    version, _ = await agents.import_version(spec, content_digest(spec))
    await agents.activate(
        agent_key="calculator-agent",
        version_id=version.id,
        expected_previous_version_id=None,
    )
    draft, _ = await DraftRepository(session, scope).create_from_active(
        "calculator-agent",
        {"nodes": [], "viewport": {"x": 0, "y": 0, "zoom": 1}},
    )
    await PublishingRepository(session, scope).publish_draft(
        "calculator-agent",
        expected_revision=draft.revision,
        expected_active_version_id=version.id,
    )
    await session.commit()


@pytest.mark.asyncio
async def test_public_service_sanitizes_metadata_and_binds_read_capability(
    database_engine: AsyncEngine,
    database_session: AsyncSession,
    request_scope: RequestScope,
) -> None:
    await _publish(database_session, request_scope)
    factory = async_sessionmaker(database_engine, expire_on_commit=False)
    run_service = FakeRunService()
    public = PublicService(
        factory,
        run_service=cast(Any, run_service),
        api_key_hash_master=b"h" * 32,
        capability_master=b"c" * 32,
        capability_ttl_seconds=3600,
        sync_wait_seconds=0.01,
        poll_interval_seconds=0.001,
        heartbeat_seconds=0.001,
        max_polls=1,
    )

    metadata = await public.get_agent("calculator-agent")
    serialized = metadata.model_dump_json()
    assert "prompt" not in serialized
    assert "tools" not in serialized

    created = await public.create_run(
        "calculator-agent",
        PublicRunCreateRequest.model_validate(
            {
                "input": {"question": "19 * 23"},
                "locale": "en-US",
            }
        ),
        idempotency_key=None,
        authorization=None,
    )
    assert created.run_capability is not None
    assert "must-not-leak" not in created.model_dump_json()
    readable = await public.get_run(
        "calculator-agent",
        UUID(created.run_id.root),
        authorization=f"Bearer {created.run_capability}",
    )
    assert readable.run_id == created.run_id
    with pytest.raises(ApiError) as wrong_agent:
        await public.get_run(
            "other-agent",
            UUID(created.run_id.root),
            authorization=f"Bearer {created.run_capability}",
        )
    assert wrong_agent.value.status_code == 401


@pytest.mark.asyncio
async def test_scoped_api_key_requires_idempotency_header(
    database_engine: AsyncEngine,
    database_session: AsyncSession,
    request_scope: RequestScope,
) -> None:
    await _publish(database_session, request_scope)
    factory = async_sessionmaker(database_engine, expire_on_commit=False)
    owner = PublishingService(
        factory,
        api_key_hash_master=b"h" * 32,
        webhook_signing_master=b"w" * 32,
        webhook_allowed_origins=[],
    )
    key = await owner.create_api_key(
        "calculator-agent",
        ApiKeyCreateRequest(
            label="Public API",
            scopes=[
                ApiKeyScope.runs_create,
                ApiKeyScope.runs_read,
                ApiKeyScope.events_read,
            ],
            expires_at=None,
        ),
        request_scope,
    )
    public = PublicService(
        factory,
        run_service=cast(Any, FakeRunService()),
        api_key_hash_master=b"h" * 32,
        capability_master=b"c" * 32,
        capability_ttl_seconds=3600,
        sync_wait_seconds=0.01,
        poll_interval_seconds=0.001,
        heartbeat_seconds=0.001,
        max_polls=1,
    )
    body = PublicRunCreateRequest.model_validate(
        {"input": {"question": "19 * 23"}, "locale": "en-US"}
    )

    with pytest.raises(ApiError) as missing_key:
        await public.create_run(
            "calculator-agent",
            body,
            idempotency_key=None,
            authorization=f"Bearer {key.secret}",
        )
    assert missing_key.value.document["code"] == "idempotency_key_required"
    created = await public.create_run(
        "calculator-agent",
        body,
        idempotency_key="acceptance-key-0001",
        authorization=f"Bearer {key.secret}",
    )
    assert created.run_capability is None
