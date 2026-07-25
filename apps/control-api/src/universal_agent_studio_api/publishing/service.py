"""Transactional owner publishing and credential lifecycle."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta
from typing import Any, Protocol
from urllib.parse import urlsplit
from uuid import UUID, uuid4

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from universal_agent_kernel.contracts.canonical import content_digest
from universal_agent_kernel.contracts.generated import (
    ApiKeyCreateRequest,
    ApiKeyCreateView,
    ApiKeyScope,
    ApiKeyView,
    EventType,
    Identifier,
    PublicationEventView,
    PublicationState,
    PublishedVersionView,
    PublishRequest,
    RollbackRequest,
    Sha256,
    Uuid,
    WebhookCreateRequest,
    WebhookCreateView,
    WebhookEventType,
    WebhookView,
)
from universal_agent_kernel.contracts.validation import validate_agent_spec
from universal_agent_platform_store.models import (
    AgentApiKey,
    AgentPublicationEvent,
    AgentVersion,
    WebhookSubscription,
)
from universal_agent_platform_store.repositories.agents import AgentRepository
from universal_agent_platform_store.repositories.drafts import DraftRevisionConflict
from universal_agent_platform_store.repositories.publishing import (
    ActiveVersionConflict,
    ApiKeyRepository,
    DraftValidationFailed,
    PublicAgentKeyConflict,
    PublicationNotFound,
    PublishingRepository,
)
from universal_agent_platform_store.repositories.webhooks import (
    WebhookNotFound,
    WebhookRepository,
)
from universal_agent_platform_store.scope import RequestScope

from universal_agent_studio_api.errors import ApiError
from universal_agent_studio_api.publishing.crypto import (
    derive_webhook_secret,
    issue_api_key,
)

KNOWN_SCOPES = frozenset(scope.value for scope in ApiKeyScope)
KNOWN_WEBHOOK_EVENTS = frozenset(event.value for event in WebhookEventType)
MAX_API_KEY_LIFETIME = timedelta(days=366)


class PublishingServicePort(Protocol):
    async def get_state(
        self, agent_id: str, scope: RequestScope
    ) -> PublicationState: ...

    async def publish(
        self, agent_id: str, body: PublishRequest, scope: RequestScope
    ) -> PublicationState: ...

    async def rollback(
        self, agent_id: str, body: RollbackRequest, scope: RequestScope
    ) -> PublicationState: ...

    async def create_api_key(
        self, agent_id: str, body: ApiKeyCreateRequest, scope: RequestScope
    ) -> ApiKeyCreateView: ...

    async def list_api_keys(
        self, agent_id: str, scope: RequestScope
    ) -> list[ApiKeyView]: ...

    async def revoke_api_key(
        self, agent_id: str, key_id: UUID, scope: RequestScope
    ) -> ApiKeyView: ...

    async def create_webhook(
        self, agent_id: str, body: WebhookCreateRequest, scope: RequestScope
    ) -> WebhookCreateView: ...

    async def list_webhooks(
        self, agent_id: str, scope: RequestScope
    ) -> list[WebhookView]: ...

    async def revoke_webhook(
        self, agent_id: str, subscription_id: UUID, scope: RequestScope
    ) -> WebhookView: ...


def validate_webhook_target(
    target_url: str,
    *,
    allowed_origins: list[str],
) -> str:
    parsed = urlsplit(target_url)
    if (
        parsed.scheme not in {"http", "https"}
        or parsed.hostname is None
        or parsed.username is not None
        or parsed.password is not None
        or bool(parsed.fragment)
    ):
        raise ValueError("webhook_origin_not_allowed")
    host = parsed.hostname
    if ":" in host and not host.startswith("["):
        host = f"[{host}]"
    origin = f"{parsed.scheme}://{host}"
    if parsed.port is not None:
        origin += f":{parsed.port}"
    normalized_allowed = {value.rstrip("/") for value in allowed_origins}
    if origin not in normalized_allowed:
        raise ValueError("webhook_origin_not_allowed")
    return target_url


class PublishingService:
    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        *,
        api_key_hash_master: bytes,
        webhook_signing_master: bytes,
        webhook_allowed_origins: list[str],
    ) -> None:
        self.session_factory = session_factory
        self.api_key_hash_master = api_key_hash_master
        self.webhook_signing_master = webhook_signing_master
        self.webhook_allowed_origins = webhook_allowed_origins

    @asynccontextmanager
    async def _transaction(self) -> AsyncIterator[AsyncSession]:
        async with self.session_factory() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    @staticmethod
    def _public_version(
        agent_id: str,
        version: AgentVersion,
    ) -> Identifier:
        return Identifier(root=f"{agent_id}-v{version.version_number}")

    @classmethod
    def _version_view(
        cls,
        agent_id: str,
        version: AgentVersion,
    ) -> PublishedVersionView:
        return PublishedVersionView(
            version_id=cls._public_version(agent_id, version),
            version_number=version.version_number,
            digest=Sha256(root=version.digest),
            created_at=version.created_at,
        )

    @classmethod
    def _event_view(
        cls,
        agent_id: str,
        event: AgentPublicationEvent,
        versions: dict[UUID, AgentVersion],
    ) -> PublicationEventView:
        previous = (
            versions.get(event.previous_version_id)
            if event.previous_version_id is not None
            else None
        )
        selected = versions[event.selected_version_id]
        return PublicationEventView(
            event_id=Uuid(root=str(event.id)),
            event_type=EventType(event.event_type),
            previous_version_id=(
                cls._public_version(agent_id, previous)
                if previous is not None
                else None
            ),
            selected_version_id=cls._public_version(agent_id, selected),
            selected_version_digest=Sha256(
                root=event.selected_version_digest
            ),
            created_at=event.created_at,
        )

    @staticmethod
    def _key_view(record: AgentApiKey) -> ApiKeyView:
        return ApiKeyView(
            key_id=Uuid(root=str(record.id)),
            label=record.label,
            prefix=record.prefix,
            scopes=[ApiKeyScope(scope) for scope in record.scopes],
            expires_at=record.expires_at,
            created_at=record.created_at,
            last_used_at=record.last_used_at,
            revoked_at=record.revoked_at,
        )

    @staticmethod
    def _webhook_view(record: WebhookSubscription) -> WebhookView:
        return WebhookView.model_validate(
            {
                "subscription_id": str(record.id),
                "label": record.label,
                "target_url": record.target_url,
                "events": record.events,
                "created_at": record.created_at,
                "revoked_at": record.revoked_at,
            }
        )

    async def _state(
        self,
        session: AsyncSession,
        agent_id: str,
        scope: RequestScope,
    ) -> PublicationState:
        state = await PublishingRepository(session, scope).get_state(agent_id)
        if state is None:
            raise ApiError(404, "publishing_state_not_found")
        versions_by_id = {version.id: version for version in state.versions}
        keys = await ApiKeyRepository(session, scope).list(agent_id)
        webhooks = await WebhookRepository(session, scope).list(agent_id)
        return PublicationState(
            schema_version="0.1.0",
            agent_id=Identifier(root=agent_id),
            draft_revision=state.draft.revision,
            draft_digest=Sha256(root=state.draft.digest),
            active_version_id=(
                self._public_version(agent_id, state.active_version)
                if state.active_version is not None
                else None
            ),
            versions=[
                self._version_view(agent_id, version)
                for version in state.versions
            ],
            events=[
                self._event_view(agent_id, event, versions_by_id)
                for event in state.events
            ],
            api_keys=[self._key_view(record) for record in keys],
            webhooks=[self._webhook_view(record) for record in webhooks],
        )

    async def get_state(
        self,
        agent_id: str,
        scope: RequestScope,
    ) -> PublicationState:
        async with self._transaction() as session:
            return await self._state(session, agent_id, scope)

    async def _internal_version_id(
        self,
        session: AsyncSession,
        scope: RequestScope,
        agent_id: str,
        public_version_id: Identifier | None,
    ) -> UUID | None:
        if public_version_id is None:
            return None
        raw_public_id = public_version_id.root
        version = await AgentRepository(
            session,
            scope,
        ).get_version_by_public_id(raw_public_id)
        if (
            version is None
            or str(version.agent_spec.get("agent_id")) != agent_id
        ):
            raise ApiError(404, "version_not_owned")
        return version.id

    async def publish(
        self,
        agent_id: str,
        body: PublishRequest,
        scope: RequestScope,
    ) -> PublicationState:
        def draft_is_publishable(
            agent_spec: dict[str, Any],
            stored_digest: str,
        ) -> bool:
            return (
                validate_agent_spec(agent_spec).valid
                and agent_spec.get("agent_id") == agent_id
                and content_digest(agent_spec) == stored_digest
            )

        async with self._transaction() as session:
            expected = await self._internal_version_id(
                session,
                scope,
                agent_id,
                body.expected_active_version_id,
            )
            try:
                await PublishingRepository(session, scope).publish_draft(
                    agent_id,
                    expected_revision=body.expected_draft_revision,
                    expected_active_version_id=expected,
                    validate_draft=draft_is_publishable,
                )
            except DraftRevisionConflict as error:
                raise ApiError(409, "draft_revision_conflict") from error
            except DraftValidationFailed as error:
                raise ApiError(422, "agent_spec_invalid") from error
            except PublicAgentKeyConflict as error:
                raise ApiError(409, "public_agent_id_conflict") from error
            except ActiveVersionConflict as error:
                raise ApiError(409, "active_version_conflict") from error
            except PublicationNotFound as error:
                raise ApiError(404, str(error)) from error
            return await self._state(session, agent_id, scope)

    async def rollback(
        self,
        agent_id: str,
        body: RollbackRequest,
        scope: RequestScope,
    ) -> PublicationState:
        async with self._transaction() as session:
            expected = await self._internal_version_id(
                session,
                scope,
                agent_id,
                body.expected_active_version_id,
            )
            target = await self._internal_version_id(
                session,
                scope,
                agent_id,
                body.target_version_id,
            )
            assert expected is not None
            assert target is not None
            try:
                await PublishingRepository(session, scope).rollback(
                    agent_id,
                    target_version_id=target,
                    expected_active_version_id=expected,
                )
            except ActiveVersionConflict as error:
                raise ApiError(409, "active_version_conflict") from error
            except PublicationNotFound as error:
                raise ApiError(404, str(error)) from error
            return await self._state(session, agent_id, scope)

    async def create_api_key(
        self,
        agent_id: str,
        body: ApiKeyCreateRequest,
        scope: RequestScope,
    ) -> ApiKeyCreateView:
        raw_scopes = [item.value for item in body.scopes]
        if not raw_scopes or not set(raw_scopes) <= KNOWN_SCOPES:
            raise ApiError(422, "invalid_api_key_scope")
        if body.expires_at is not None:
            now = datetime.now(UTC)
            if (
                body.expires_at <= now
                or body.expires_at > now + MAX_API_KEY_LIFETIME
            ):
                raise ApiError(422, "invalid_api_key_expiry")
        issued = issue_api_key(self.api_key_hash_master)
        async with self._transaction() as session:
            try:
                record = await ApiKeyRepository(session, scope).create(
                    agent_id,
                    label=body.label,
                    prefix=issued.prefix,
                    key_hash=issued.key_hash,
                    scopes=raw_scopes,
                    expires_at=body.expires_at,
                )
            except PublicationNotFound as error:
                raise ApiError(404, str(error)) from error
            view = self._key_view(record)
            return ApiKeyCreateView(
                **view.model_dump(),
                secret=issued.raw,
            )

    async def list_api_keys(
        self,
        agent_id: str,
        scope: RequestScope,
    ) -> list[ApiKeyView]:
        async with self._transaction() as session:
            try:
                records = await ApiKeyRepository(session, scope).list(agent_id)
            except PublicationNotFound as error:
                raise ApiError(404, str(error)) from error
            return [self._key_view(record) for record in records]

    async def revoke_api_key(
        self,
        agent_id: str,
        key_id: UUID,
        scope: RequestScope,
    ) -> ApiKeyView:
        async with self._transaction() as session:
            try:
                record = await ApiKeyRepository(session, scope).revoke(
                    agent_id,
                    key_id,
                )
            except PublicationNotFound as error:
                raise ApiError(404, str(error)) from error
            if record is None:
                raise ApiError(404, "api_key_not_found")
            return self._key_view(record)

    async def create_webhook(
        self,
        agent_id: str,
        body: WebhookCreateRequest,
        scope: RequestScope,
    ) -> WebhookCreateView:
        events = [event.value for event in body.events]
        if not events or not set(events) <= KNOWN_WEBHOOK_EVENTS:
            raise ApiError(422, "invalid_webhook_event")
        try:
            target_url = validate_webhook_target(
                str(body.target_url),
                allowed_origins=self.webhook_allowed_origins,
            )
        except ValueError as error:
            raise ApiError(422, "webhook_origin_not_allowed") from error
        signing_key_id = uuid4()
        async with self._transaction() as session:
            try:
                record = await WebhookRepository(session, scope).create(
                    agent_id,
                    label=body.label,
                    target_url=target_url,
                    events=events,
                    signing_key_id=signing_key_id,
                )
            except WebhookNotFound as error:
                raise ApiError(404, str(error)) from error
            view = self._webhook_view(record)
            return WebhookCreateView(
                **view.model_dump(),
                secret=derive_webhook_secret(
                    self.webhook_signing_master,
                    signing_key_id,
                ),
            )

    async def list_webhooks(
        self,
        agent_id: str,
        scope: RequestScope,
    ) -> list[WebhookView]:
        async with self._transaction() as session:
            try:
                records = await WebhookRepository(session, scope).list(agent_id)
            except WebhookNotFound as error:
                raise ApiError(404, str(error)) from error
            return [self._webhook_view(record) for record in records]

    async def revoke_webhook(
        self,
        agent_id: str,
        subscription_id: UUID,
        scope: RequestScope,
    ) -> WebhookView:
        async with self._transaction() as session:
            try:
                record = await WebhookRepository(session, scope).revoke(
                    agent_id,
                    subscription_id,
                )
            except WebhookNotFound as error:
                raise ApiError(404, str(error)) from error
            if record is None:
                raise ApiError(404, "webhook_not_found")
            return self._webhook_view(record)
