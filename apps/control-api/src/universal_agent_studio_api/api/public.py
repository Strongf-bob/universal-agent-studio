"""Sanitized public agent and run API."""

from __future__ import annotations

from typing import Annotated, cast
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Request, Response, status
from fastapi.responses import StreamingResponse
from universal_agent_kernel.contracts.generated import (
    PublicAgentView,
    PublicRunCreateRequest,
    PublicRunView,
)

from universal_agent_studio_api.errors import ApiError
from universal_agent_studio_api.publishing.public_service import PublicServicePort

router = APIRouter(prefix="/public/v1/agents", tags=["public-agents"])


def public_service(request: Request) -> PublicServicePort:
    return cast(PublicServicePort, request.app.state.public_service)


@router.get("/{agent_id}", response_model=PublicAgentView)
async def get_public_agent(
    agent_id: str,
    service: Annotated[PublicServicePort, Depends(public_service)],
) -> PublicAgentView:
    return await service.get_agent(agent_id)


@router.post(
    "/{agent_id}/runs",
    response_model=PublicRunView,
    status_code=status.HTTP_202_ACCEPTED,
)
async def create_public_run(
    agent_id: str,
    body: PublicRunCreateRequest,
    service: Annotated[PublicServicePort, Depends(public_service)],
    authorization: Annotated[
        str | None,
        Header(alias="Authorization"),
    ] = None,
    idempotency_key: Annotated[
        str | None,
        Header(alias="Idempotency-Key"),
    ] = None,
) -> PublicRunView:
    return await service.create_run(
        agent_id,
        body,
        idempotency_key=idempotency_key,
        authorization=authorization,
    )


@router.post("/{agent_id}/invoke", response_model=PublicRunView)
async def invoke_public_agent(
    agent_id: str,
    body: PublicRunCreateRequest,
    response: Response,
    service: Annotated[PublicServicePort, Depends(public_service)],
    authorization: Annotated[
        str | None,
        Header(alias="Authorization"),
    ] = None,
    idempotency_key: Annotated[
        str | None,
        Header(alias="Idempotency-Key"),
    ] = None,
) -> PublicRunView:
    view = await service.invoke(
        agent_id,
        body,
        idempotency_key=idempotency_key,
        authorization=authorization,
    )
    if view.status.value not in {"completed", "failed", "cancelled"}:
        response.status_code = status.HTTP_202_ACCEPTED
    return view


@router.get("/{agent_id}/runs/{run_id}", response_model=PublicRunView)
async def get_public_run(
    agent_id: str,
    run_id: UUID,
    service: Annotated[PublicServicePort, Depends(public_service)],
    authorization: Annotated[
        str | None,
        Header(alias="Authorization"),
    ] = None,
) -> PublicRunView:
    return await service.get_run(
        agent_id,
        run_id,
        authorization=authorization,
    )


@router.get("/{agent_id}/runs/{run_id}/events")
async def get_public_events(
    request: Request,
    agent_id: str,
    run_id: UUID,
    service: Annotated[PublicServicePort, Depends(public_service)],
    authorization: Annotated[
        str | None,
        Header(alias="Authorization"),
    ] = None,
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
        if after_sequence < 0 or after_sequence > 9_223_372_036_854_775_807:
            raise ApiError(400, "last_event_id_invalid")
    await service.authorize_events(
        agent_id,
        run_id,
        authorization=authorization,
    )
    return StreamingResponse(
        service.stream_events(
            request,
            agent_id,
            run_id,
            authorization=authorization,
            after_sequence=after_sequence,
        ),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )
