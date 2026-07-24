"""Authenticated run, cancellation, SSE and trace endpoints."""

from __future__ import annotations

from typing import Annotated, Any, cast
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Request, Response, status
from fastapi.responses import StreamingResponse
from universal_agent_platform_store.scope import RequestScope

from universal_agent_studio_api.auth.dependencies import (
    authenticated_owner,
    csrf_authenticated_owner,
)
from universal_agent_studio_api.auth.models import AuthenticatedOwner
from universal_agent_studio_api.errors import ApiError
from universal_agent_studio_api.runs.service import (
    CancelRunView,
    CreateRunRequest,
    CreateRunView,
    RunService,
    RunView,
)
from universal_agent_studio_api.runs.sse import stream_run_events
from universal_agent_studio_api.settings import Settings

router = APIRouter(prefix="/api/v1/runs", tags=["runs"])


def run_service(request: Request) -> RunService:
    return cast(RunService, request.app.state.run_service)


def _scope(authenticated: AuthenticatedOwner) -> RequestScope:
    return RequestScope(
        workspace_id=authenticated.owner.workspace_id,
        project_id=authenticated.owner.project_id,
        owner_id=authenticated.owner.id,
    )


@router.post("", response_model=CreateRunView)
async def create_run(
    body: CreateRunRequest,
    response: Response,
    authenticated: Annotated[
        AuthenticatedOwner,
        Depends(csrf_authenticated_owner),
    ],
    service: Annotated[RunService, Depends(run_service)],
) -> CreateRunView:
    created = await service.create_run(body, _scope(authenticated))
    response.status_code = (
        status.HTTP_200_OK if created.reused else status.HTTP_201_CREATED
    )
    return created


@router.get("/{run_id}", response_model=RunView)
async def get_run(
    run_id: UUID,
    authenticated: Annotated[
        AuthenticatedOwner,
        Depends(authenticated_owner),
    ],
    service: Annotated[RunService, Depends(run_service)],
) -> RunView:
    return await service.get_run(run_id, _scope(authenticated))


@router.post(
    "/{run_id}/cancel",
    response_model=CancelRunView,
    status_code=status.HTTP_202_ACCEPTED,
)
async def cancel_run(
    run_id: UUID,
    authenticated: Annotated[
        AuthenticatedOwner,
        Depends(csrf_authenticated_owner),
    ],
    service: Annotated[RunService, Depends(run_service)],
) -> CancelRunView:
    return await service.cancel_run(run_id, _scope(authenticated))


@router.get("/{run_id}/trace")
async def get_trace(
    run_id: UUID,
    authenticated: Annotated[
        AuthenticatedOwner,
        Depends(authenticated_owner),
    ],
    service: Annotated[RunService, Depends(run_service)],
) -> dict[str, Any]:
    return await service.get_trace(run_id, _scope(authenticated))


@router.get("/{run_id}/events")
async def get_events(
    request: Request,
    run_id: UUID,
    authenticated: Annotated[
        AuthenticatedOwner,
        Depends(authenticated_owner),
    ],
    service: Annotated[RunService, Depends(run_service)],
    last_event_id: Annotated[
        str | None,
        Header(alias="Last-Event-ID"),
    ] = None,
) -> StreamingResponse:
    if last_event_id is None:
        after_sequence = 0
    else:
        try:
            after_sequence = int(last_event_id)
        except ValueError as error:
            raise ApiError(400, "last_event_id_invalid") from error
        if after_sequence < 0:
            raise ApiError(400, "last_event_id_invalid")

    scope = _scope(authenticated)
    await service.get_run(run_id, scope)
    settings = cast(Settings, request.app.state.settings)
    return StreamingResponse(
        stream_run_events(
            request=request,
            service=service,
            scope=scope,
            run_id=run_id,
            after_sequence=after_sequence,
            poll_interval_seconds=settings.sse_poll_interval_seconds,
            heartbeat_seconds=settings.sse_heartbeat_seconds,
            max_polls=settings.sse_max_polls,
        ),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )
