"""FastAPI auth dependencies derived only from the opaque session cookie."""

from __future__ import annotations

from typing import Annotated, cast

from fastapi import Cookie, Depends, Header, Request

from universal_agent_studio_api.auth.models import AuthenticatedOwner
from universal_agent_studio_api.auth.service import AuthService


def auth_service(request: Request) -> AuthService:
    return cast(AuthService, request.app.state.auth_service)


async def authenticated_owner(
    service: Annotated[AuthService, Depends(auth_service)],
    session_token: Annotated[str | None, Cookie(alias="uas_session")] = None,
) -> AuthenticatedOwner:
    authenticated = await service.authenticate(session_token)
    assert authenticated is not None
    return authenticated


async def csrf_authenticated_owner(
    service: Annotated[AuthService, Depends(auth_service)],
    authenticated: Annotated[
        AuthenticatedOwner,
        Depends(authenticated_owner),
    ],
    csrf_token: Annotated[
        str | None,
        Header(alias="X-CSRF-Token"),
    ] = None,
) -> AuthenticatedOwner:
    service.require_csrf(authenticated, csrf_token)
    return authenticated
