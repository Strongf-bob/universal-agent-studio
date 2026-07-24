from typing import Annotated

from fastapi import APIRouter, Cookie, Depends, Response, status

from universal_agent_studio_api.api.bootstrap import _set_session_cookie
from universal_agent_studio_api.auth.dependencies import (
    auth_service,
    authenticated_owner,
    csrf_authenticated_owner,
)
from universal_agent_studio_api.auth.models import (
    AuthenticatedOwner,
    LoginRequest,
)
from universal_agent_studio_api.auth.service import AuthService

router = APIRouter(prefix="/api/v1/session", tags=["session"])


def _clear_session_cookie(response: Response, service: AuthService) -> None:
    response.delete_cookie(
        "uas_session",
        httponly=True,
        secure=service.settings.secure_cookies,
        samesite="lax",
        path="/",
    )


@router.post("", status_code=status.HTTP_201_CREATED)
async def login(
    body: LoginRequest,
    response: Response,
    service: Annotated[AuthService, Depends(auth_service)],
    current_token: Annotated[
        str | None,
        Cookie(alias="uas_session"),
    ] = None,
) -> dict[str, object]:
    material = await service.login(
        login_name=body.login_name,
        password=body.password.get_secret_value(),
        current_token=current_token,
    )
    _set_session_cookie(response, material.raw_session_token, service.settings)
    return {
        "owner": {
            "login_name": material.owner.login_name,
            "preferred_locale": material.owner.preferred_locale,
        },
        "csrf_token": material.raw_csrf_token,
    }


@router.get("")
async def current_session(
    authenticated: Annotated[
        AuthenticatedOwner,
        Depends(authenticated_owner),
    ],
    service: Annotated[AuthService, Depends(auth_service)],
) -> dict[str, object]:
    csrf_token = await service.rotate_csrf(authenticated)
    return {
        "owner": {
            "login_name": authenticated.owner.login_name,
            "preferred_locale": authenticated.owner.preferred_locale,
        },
        "csrf_token": csrf_token,
    }


@router.delete("", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    response: Response,
    authenticated: Annotated[
        AuthenticatedOwner,
        Depends(csrf_authenticated_owner),
    ],
    service: Annotated[AuthService, Depends(auth_service)],
) -> None:
    await service.logout(authenticated)
    _clear_session_cookie(response, service)
