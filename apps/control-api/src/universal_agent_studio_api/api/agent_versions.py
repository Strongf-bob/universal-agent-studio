"""Authenticated immutable AgentVersion HTTP API."""

from __future__ import annotations

from typing import Annotated, cast

from fastapi import APIRouter, Depends, Request, Response, status
from universal_agent_platform_store.scope import RequestScope

from universal_agent_studio_api.agents.models import (
    ActivateAgentVersionRequest,
    ActiveAgentVersionView,
    AgentVersionImportView,
    AgentVersionView,
)
from universal_agent_studio_api.agents.service import AgentVersionService
from universal_agent_studio_api.auth.dependencies import (
    authenticated_owner,
    csrf_authenticated_owner,
)
from universal_agent_studio_api.auth.models import AuthenticatedOwner

router = APIRouter(prefix="/api/v1", tags=["agent-versions"])


def agent_version_service(request: Request) -> AgentVersionService:
    return cast(AgentVersionService, request.app.state.agent_version_service)


def _scope(authenticated: AuthenticatedOwner) -> RequestScope:
    return RequestScope(
        workspace_id=authenticated.owner.workspace_id,
        project_id=authenticated.owner.project_id,
        owner_id=authenticated.owner.id,
    )


@router.post(
    "/agent-versions/import",
    response_model=AgentVersionImportView,
)
async def import_agent_version(
    request: Request,
    response: Response,
    authenticated: Annotated[
        AuthenticatedOwner,
        Depends(csrf_authenticated_owner),
    ],
    service: Annotated[AgentVersionService, Depends(agent_version_service)],
) -> AgentVersionImportView:
    imported = await service.import_raw(await request.body(), _scope(authenticated))
    response.status_code = (
        status.HTTP_200_OK if imported.reused else status.HTTP_201_CREATED
    )
    return imported


@router.get(
    "/agent-versions/{version_id}",
    response_model=AgentVersionView,
)
async def get_agent_version(
    version_id: str,
    authenticated: Annotated[
        AuthenticatedOwner,
        Depends(authenticated_owner),
    ],
    service: Annotated[AgentVersionService, Depends(agent_version_service)],
) -> AgentVersionView:
    return await service.get_version(version_id, _scope(authenticated))


@router.post(
    "/agents/{agent_id}/active-version",
    response_model=ActiveAgentVersionView,
)
async def activate_agent_version(
    agent_id: str,
    body: ActivateAgentVersionRequest,
    authenticated: Annotated[
        AuthenticatedOwner,
        Depends(csrf_authenticated_owner),
    ],
    service: Annotated[AgentVersionService, Depends(agent_version_service)],
) -> ActiveAgentVersionView:
    return await service.activate(
        agent_id=agent_id,
        version_id=body.version_id,
        expected_previous_version_id=body.expected_previous_version_id,
        scope=_scope(authenticated),
    )
