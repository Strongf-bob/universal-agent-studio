from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any, cast

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker
from universal_agent_kernel.contracts.canonical import content_digest
from universal_agent_kernel.contracts.generated import (
    ApiKeyCreateRequest,
    ApiKeyScope,
    WebhookCreateRequest,
    WebhookEventType,
)
from universal_agent_platform_store.models import (
    AgentApiKey,
    AgentPublicationEvent,
    AgentVersion,
    Base,
)
from universal_agent_platform_store.repositories.agents import AgentRepository
from universal_agent_platform_store.repositories.drafts import DraftRepository
from universal_agent_platform_store.repositories.publishing import (
    DraftRevisionConflict,
    PublishingRepository,
)
from universal_agent_platform_store.scope import RequestScope
from universal_agent_studio_api.publishing.service import PublishingService

ROOT = Path(__file__).parents[2]
GOLDEN = (
    ROOT
    / "contracts"
    / "examples"
    / "v0.1.0"
    / "valid"
    / "agent.calculator.ru-en.json"
)


def _spec() -> dict[str, Any]:
    return cast(dict[str, Any], json.loads(GOLDEN.read_text(encoding="utf-8")))


async def _seed(
    session: AsyncSession,
    scope: RequestScope,
) -> tuple[AgentVersion, int]:
    agents = AgentRepository(session, scope)
    spec = _spec()
    base, _ = await agents.import_version(spec, content_digest(spec))
    await agents.activate(
        agent_key=str(spec["agent_id"]),
        version_id=base.id,
        expected_previous_version_id=None,
    )
    draft, _ = await DraftRepository(session, scope).create_from_active(
        str(spec["agent_id"]),
        {"nodes": [], "viewport": {"x": 0, "y": 0, "zoom": 1}},
    )
    await session.commit()
    return base, draft.revision


def test_slice3_tables_are_part_of_platform_metadata() -> None:
    assert {
        "agent_publication_events",
        "agent_api_keys",
        "webhook_subscriptions",
        "webhook_deliveries",
    } <= set(Base.metadata.tables)


@pytest.mark.asyncio
async def test_publish_v2_then_rollback_preserves_immutable_versions(
    database_session: AsyncSession,
    request_scope: RequestScope,
) -> None:
    base, revision = await _seed(database_session, request_scope)
    drafts = DraftRepository(database_session, request_scope)
    changed = copy.deepcopy(_spec())
    changed["localized_metadata"]["name"]["en-US"] = "Calculator v2"
    draft = await drafts.update(
        "calculator-agent",
        expected_revision=revision,
        agent_spec=changed,
        digest=content_digest(changed),
        layout={"nodes": [], "viewport": {"x": 0, "y": 0, "zoom": 1}},
    )
    await database_session.commit()
    repository = PublishingRepository(database_session, request_scope)

    published = await repository.publish_draft(
        "calculator-agent",
        expected_revision=draft.revision,
        expected_active_version_id=base.id,
    )
    await database_session.commit()
    v2_document = copy.deepcopy(published.version.agent_spec)
    rolled_back = await repository.rollback(
        "calculator-agent",
        target_version_id=base.id,
        expected_active_version_id=published.version.id,
    )
    await database_session.commit()

    assert rolled_back.version.id == base.id
    persisted_v2 = await database_session.get(AgentVersion, published.version.id)
    assert persisted_v2 is not None
    assert persisted_v2.agent_spec == v2_document
    events = list(
        await database_session.scalars(
            select(AgentPublicationEvent).order_by(
                AgentPublicationEvent.created_at,
                AgentPublicationEvent.id,
            )
        )
    )
    assert [event.event_type for event in events] == ["publish", "rollback"]


@pytest.mark.asyncio
async def test_first_explicit_publish_records_existing_active_version(
    database_session: AsyncSession,
    request_scope: RequestScope,
) -> None:
    base, revision = await _seed(database_session, request_scope)

    published = await PublishingRepository(
        database_session,
        request_scope,
    ).publish_draft(
        "calculator-agent",
        expected_revision=revision,
        expected_active_version_id=base.id,
    )
    await database_session.commit()

    assert published.version.id == base.id
    assert published.reused is True
    assert published.event is not None
    assert published.event.event_type == "publish"


@pytest.mark.asyncio
async def test_stale_draft_revision_does_not_publish(
    database_session: AsyncSession,
    request_scope: RequestScope,
) -> None:
    base, revision = await _seed(database_session, request_scope)

    with pytest.raises(DraftRevisionConflict):
        await PublishingRepository(
            database_session,
            request_scope,
        ).publish_draft(
            "calculator-agent",
            expected_revision=revision + 1,
            expected_active_version_id=base.id,
        )

    assert (
        await database_session.scalar(
            select(AgentPublicationEvent).where(
                AgentPublicationEvent.agent_id == base.agent_id
            )
        )
        is None
    )


@pytest.mark.asyncio
async def test_issued_secrets_are_not_persisted_as_plaintext(
    database_engine: AsyncEngine,
    database_session: AsyncSession,
    request_scope: RequestScope,
) -> None:
    await _seed(database_session, request_scope)
    service = PublishingService(
        async_sessionmaker(database_engine, expire_on_commit=False),
        api_key_hash_master=b"h" * 32,
        webhook_signing_master=b"w" * 32,
        webhook_allowed_origins=["http://example.test:9090"],
    )

    api_key = await service.create_api_key(
        "calculator-agent",
        ApiKeyCreateRequest(
            label="Acceptance",
            scopes=[ApiKeyScope.runs_create],
            expires_at=None,
        ),
        request_scope,
    )
    webhook = await service.create_webhook(
        "calculator-agent",
        WebhookCreateRequest.model_validate(
            {
                "label": "Acceptance",
                "target_url": "http://example.test:9090/hooks/terminal",
                "events": [WebhookEventType.run_completed.value],
            }
        ),
        request_scope,
    )

    async with AsyncSession(database_engine) as verification:
        stored_key = await verification.scalar(select(AgentApiKey))
        assert stored_key is not None
        assert stored_key.key_hash != api_key.secret
        serialized_rows = json.dumps(
            {
                "key_hash": stored_key.key_hash,
                "webhook_secret": None,
            }
        )
    assert api_key.secret not in serialized_rows
    assert webhook.secret not in serialized_rows
