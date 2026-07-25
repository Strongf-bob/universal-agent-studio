from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import UUID

import pytest
from conftest import MemoryAgentVersionPersistence, MemoryAuthStore
from httpx import ASGITransport, AsyncClient
from universal_agent_kernel.contracts.generated import (
    ApiKeyCreateRequest,
    ApiKeyCreateView,
    ApiKeyScope,
    ApiKeyView,
    Identifier,
    PublicationState,
    PublishedVersionView,
    PublishRequest,
    RollbackRequest,
    Sha256,
    Uuid,
    WebhookCreateRequest,
    WebhookCreateView,
    WebhookView,
)
from universal_agent_studio_api.main import create_app
from universal_agent_studio_api.settings import Settings


class FakePublishingService:
    def __init__(self) -> None:
        self.state = PublicationState(
            schema_version="0.1.0",
            agent_id=Identifier(root="calculator-agent"),
            draft_revision=2,
            draft_digest=Sha256(root="a" * 64),
            active_version_id=Identifier(root="calculator-agent-v1"),
            versions=[
                PublishedVersionView(
                    version_id=Identifier(root="calculator-agent-v1"),
                    version_number=1,
                    digest=Sha256(root="b" * 64),
                    created_at=datetime(2026, 7, 25, tzinfo=UTC),
                )
            ],
            events=[],
            api_keys=[],
            webhooks=[],
        )
        self.publish_body: PublishRequest | None = None
        self.rollback_body: RollbackRequest | None = None

    async def get_state(self, agent_id: str, scope: object) -> PublicationState:
        del scope
        assert agent_id == "calculator-agent"
        return self.state

    async def publish(
        self,
        agent_id: str,
        body: PublishRequest,
        scope: object,
    ) -> PublicationState:
        del agent_id, scope
        self.publish_body = body
        return self.state

    async def rollback(
        self,
        agent_id: str,
        body: RollbackRequest,
        scope: object,
    ) -> PublicationState:
        del agent_id, scope
        self.rollback_body = body
        return self.state

    async def create_api_key(
        self,
        agent_id: str,
        body: ApiKeyCreateRequest,
        scope: object,
    ) -> ApiKeyCreateView:
        del agent_id, scope
        return ApiKeyCreateView(
            key_id=Uuid(root="11111111-1111-4111-8111-111111111111"),
            label=body.label,
            prefix="0123456789abcdef",
            scopes=body.scopes,
            expires_at=body.expires_at,
            created_at=datetime(2026, 7, 25, tzinfo=UTC),
            last_used_at=None,
            revoked_at=None,
            secret="uas_live_0123456789abcdef_" + "A" * 43,
        )

    async def list_api_keys(
        self,
        agent_id: str,
        scope: object,
    ) -> list[ApiKeyView]:
        del agent_id, scope
        return []

    async def revoke_api_key(
        self,
        agent_id: str,
        key_id: UUID,
        scope: object,
    ) -> ApiKeyView:
        del agent_id, key_id, scope
        raise AssertionError("not exercised")

    async def create_webhook(
        self,
        agent_id: str,
        body: WebhookCreateRequest,
        scope: object,
    ) -> WebhookCreateView:
        del agent_id, body, scope
        raise AssertionError("not exercised")

    async def list_webhooks(
        self,
        agent_id: str,
        scope: object,
    ) -> list[WebhookView]:
        del agent_id, scope
        return []

    async def revoke_webhook(
        self,
        agent_id: str,
        subscription_id: UUID,
        scope: object,
    ) -> WebhookView:
        del agent_id, subscription_id, scope
        raise AssertionError("not exercised")


@pytest.mark.asyncio
async def test_owner_publish_and_key_routes_require_session_and_csrf() -> None:
    auth_store = MemoryAuthStore()
    publishing = FakePublishingService()
    app = create_app(
        auth_store=auth_store,
        agent_persistence=MemoryAgentVersionPersistence(),
        publishing_service=publishing,
        settings=Settings(
            allowed_hosts=["testserver"],
            allowed_origins=["http://testserver"],
            secure_cookies=False,
        ),
    )
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
        headers={"Origin": "http://testserver"},
    ) as client:
        bootstrap = await client.post(
            "/api/v1/bootstrap/owner",
            json={
                "login_name": "owner",
                "password": "correct horse battery staple",
                "preferred_locale": "en-US",
            },
        )
        csrf = bootstrap.json()["csrf_token"]
        state = await client.get(
            "/api/v1/agents/calculator-agent/publishing"
        )
        published = await client.post(
            "/api/v1/agents/calculator-agent/publish",
            headers={"X-CSRF-Token": csrf},
            json={
                "expected_draft_revision": 2,
                "expected_active_version_id": "calculator-agent-v1",
            },
        )
        key = await client.post(
            "/api/v1/agents/calculator-agent/api-keys",
            headers={"X-CSRF-Token": csrf},
            json={
                "label": "Local client",
                "scopes": [ApiKeyScope.runs_create.value],
                "expires_at": None,
            },
        )

    assert state.status_code == 200
    assert published.status_code == 200
    assert publishing.publish_body is not None
    assert publishing.publish_body.expected_draft_revision == 2
    assert key.status_code == 201
    key_document: dict[str, Any] = key.json()
    assert key_document["secret"].startswith("uas_live_")


@pytest.mark.asyncio
async def test_api_key_creation_is_rate_limited() -> None:
    auth_store = MemoryAuthStore()
    app = create_app(
        auth_store=auth_store,
        agent_persistence=MemoryAgentVersionPersistence(),
        publishing_service=FakePublishingService(),
        settings=Settings(
            allowed_hosts=["testserver"],
            allowed_origins=["http://testserver"],
            auth_rate_limit=1,
            auth_rate_window_seconds=60,
            secure_cookies=False,
        ),
    )
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
        headers={"Origin": "http://testserver"},
    ) as client:
        bootstrap = await client.post(
            "/api/v1/bootstrap/owner",
            json={
                "login_name": "owner",
                "password": "correct horse battery staple",
                "preferred_locale": "en-US",
            },
        )
        csrf = bootstrap.json()["csrf_token"]
        body = {
            "label": "Local client",
            "scopes": ["runs:create"],
            "expires_at": None,
        }
        first = await client.post(
            "/api/v1/agents/calculator-agent/api-keys",
            headers={"X-CSRF-Token": csrf},
            json=body,
        )
        second = await client.post(
            "/api/v1/agents/calculator-agent/api-keys",
            headers={"X-CSRF-Token": csrf},
            json=body,
        )

    assert first.status_code == 201
    assert second.status_code == 429
