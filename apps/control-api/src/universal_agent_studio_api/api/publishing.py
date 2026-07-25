"""Authenticated owner publishing and credential API."""

from __future__ import annotations

from typing import Annotated, cast
from uuid import UUID

from fastapi import APIRouter, Depends, Request, status
from universal_agent_kernel.contracts.generated import (
    ApiKeyCreateRequest,
    ApiKeyCreateView,
    ApiKeyView,
    PublicationState,
    PublishRequest,
    RollbackRequest,
    WebhookCreateRequest,
    WebhookCreateView,
    WebhookView,
)
from universal_agent_platform_store.scope import RequestScope

from universal_agent_studio_api.auth.dependencies import (
    authenticated_owner,
    csrf_authenticated_owner,
)
from universal_agent_studio_api.auth.models import AuthenticatedOwner
from universal_agent_studio_api.publishing.service import PublishingServicePort

router = APIRouter(prefix="/api/v1/agents", tags=["publishing"])


def publishing_service(request: Request) -> PublishingServicePort:
    return cast(PublishingServicePort, request.app.state.publishing_service)


def _scope(authenticated: AuthenticatedOwner) -> RequestScope:
    return RequestScope(
        workspace_id=authenticated.owner.workspace_id,
        project_id=authenticated.owner.project_id,
        owner_id=authenticated.owner.id,
    )


@router.get("/{agent_id}/publishing", response_model=PublicationState)
async def get_publishing_state(
    agent_id: str,
    authenticated: Annotated[
        AuthenticatedOwner,
        Depends(authenticated_owner),
    ],
    service: Annotated[PublishingServicePort, Depends(publishing_service)],
) -> PublicationState:
    return await service.get_state(agent_id, _scope(authenticated))


@router.post("/{agent_id}/publish", response_model=PublicationState)
async def publish_agent(
    agent_id: str,
    body: PublishRequest,
    authenticated: Annotated[
        AuthenticatedOwner,
        Depends(csrf_authenticated_owner),
    ],
    service: Annotated[PublishingServicePort, Depends(publishing_service)],
) -> PublicationState:
    return await service.publish(agent_id, body, _scope(authenticated))


@router.post("/{agent_id}/rollback", response_model=PublicationState)
async def rollback_agent(
    agent_id: str,
    body: RollbackRequest,
    authenticated: Annotated[
        AuthenticatedOwner,
        Depends(csrf_authenticated_owner),
    ],
    service: Annotated[PublishingServicePort, Depends(publishing_service)],
) -> PublicationState:
    return await service.rollback(agent_id, body, _scope(authenticated))


@router.post(
    "/{agent_id}/api-keys",
    response_model=ApiKeyCreateView,
    status_code=status.HTTP_201_CREATED,
)
async def create_api_key(
    agent_id: str,
    body: ApiKeyCreateRequest,
    authenticated: Annotated[
        AuthenticatedOwner,
        Depends(csrf_authenticated_owner),
    ],
    service: Annotated[PublishingServicePort, Depends(publishing_service)],
) -> ApiKeyCreateView:
    return await service.create_api_key(agent_id, body, _scope(authenticated))


@router.get("/{agent_id}/api-keys", response_model=list[ApiKeyView])
async def list_api_keys(
    agent_id: str,
    authenticated: Annotated[
        AuthenticatedOwner,
        Depends(authenticated_owner),
    ],
    service: Annotated[PublishingServicePort, Depends(publishing_service)],
) -> list[ApiKeyView]:
    return await service.list_api_keys(agent_id, _scope(authenticated))


@router.post(
    "/{agent_id}/api-keys/{key_id}/revoke",
    response_model=ApiKeyView,
)
async def revoke_api_key(
    agent_id: str,
    key_id: UUID,
    authenticated: Annotated[
        AuthenticatedOwner,
        Depends(csrf_authenticated_owner),
    ],
    service: Annotated[PublishingServicePort, Depends(publishing_service)],
) -> ApiKeyView:
    return await service.revoke_api_key(
        agent_id,
        key_id,
        _scope(authenticated),
    )


@router.post(
    "/{agent_id}/webhooks",
    response_model=WebhookCreateView,
    status_code=status.HTTP_201_CREATED,
)
async def create_webhook(
    agent_id: str,
    body: WebhookCreateRequest,
    authenticated: Annotated[
        AuthenticatedOwner,
        Depends(csrf_authenticated_owner),
    ],
    service: Annotated[PublishingServicePort, Depends(publishing_service)],
) -> WebhookCreateView:
    return await service.create_webhook(agent_id, body, _scope(authenticated))


@router.get("/{agent_id}/webhooks", response_model=list[WebhookView])
async def list_webhooks(
    agent_id: str,
    authenticated: Annotated[
        AuthenticatedOwner,
        Depends(authenticated_owner),
    ],
    service: Annotated[PublishingServicePort, Depends(publishing_service)],
) -> list[WebhookView]:
    return await service.list_webhooks(agent_id, _scope(authenticated))


@router.post(
    "/{agent_id}/webhooks/{subscription_id}/revoke",
    response_model=WebhookView,
)
async def revoke_webhook(
    agent_id: str,
    subscription_id: UUID,
    authenticated: Annotated[
        AuthenticatedOwner,
        Depends(csrf_authenticated_owner),
    ],
    service: Annotated[PublishingServicePort, Depends(publishing_service)],
) -> WebhookView:
    return await service.revoke_webhook(
        agent_id,
        subscription_id,
        _scope(authenticated),
    )
