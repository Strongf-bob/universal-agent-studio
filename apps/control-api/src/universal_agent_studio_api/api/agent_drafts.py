"""Authenticated mutable AgentDraft HTTP API."""

from __future__ import annotations

from typing import Annotated, cast

from fastapi import APIRouter, Depends, Request, Response, status
from universal_agent_platform_store.scope import RequestScope

from universal_agent_studio_api.agents.draft_service import DraftService
from universal_agent_studio_api.agents.drafts import (
    AgentDraftView,
    DraftDiffRequest,
    DraftDiffView,
    UpdateAgentDraftRequest,
)
from universal_agent_studio_api.auth.dependencies import (
    authenticated_owner,
    csrf_authenticated_owner,
)
from universal_agent_studio_api.auth.models import AuthenticatedOwner

router = APIRouter(prefix="/api/v1/agents", tags=["agent-drafts"])


def draft_service(request: Request) -> DraftService:
    return cast(DraftService, request.app.state.draft_service)


def _scope(authenticated: AuthenticatedOwner) -> RequestScope:
    return RequestScope(
        workspace_id=authenticated.owner.workspace_id,
        project_id=authenticated.owner.project_id,
        owner_id=authenticated.owner.id,
    )


@router.post(
    "/{agent_id}/draft",
    response_model=AgentDraftView,
)
async def create_agent_draft(
    agent_id: str,
    response: Response,
    authenticated: Annotated[
        AuthenticatedOwner,
        Depends(csrf_authenticated_owner),
    ],
    service: Annotated[DraftService, Depends(draft_service)],
) -> AgentDraftView:
    draft, created = await service.create(
        agent_id,
        _scope(authenticated),
    )
    response.status_code = (
        status.HTTP_201_CREATED if created else status.HTTP_200_OK
    )
    return draft


@router.get(
    "/{agent_id}/draft",
    response_model=AgentDraftView,
)
async def get_agent_draft(
    agent_id: str,
    authenticated: Annotated[
        AuthenticatedOwner,
        Depends(authenticated_owner),
    ],
    service: Annotated[DraftService, Depends(draft_service)],
) -> AgentDraftView:
    return await service.get(agent_id, _scope(authenticated))


@router.put(
    "/{agent_id}/draft",
    response_model=AgentDraftView,
)
async def update_agent_draft(
    agent_id: str,
    body: UpdateAgentDraftRequest,
    authenticated: Annotated[
        AuthenticatedOwner,
        Depends(csrf_authenticated_owner),
    ],
    service: Annotated[DraftService, Depends(draft_service)],
) -> AgentDraftView:
    return await service.update(
        agent_id,
        body,
        _scope(authenticated),
    )


@router.post(
    "/{agent_id}/draft/diff",
    response_model=DraftDiffView,
)
async def preview_agent_draft_diff(
    agent_id: str,
    body: DraftDiffRequest,
    authenticated: Annotated[
        AuthenticatedOwner,
        Depends(csrf_authenticated_owner),
    ],
    service: Annotated[DraftService, Depends(draft_service)],
) -> DraftDiffView:
    return await service.preview_diff(
        agent_id,
        body,
        _scope(authenticated),
    )
