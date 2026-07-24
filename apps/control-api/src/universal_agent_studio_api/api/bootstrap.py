from typing import Annotated

from fastapi import APIRouter, Depends, Response, status

from universal_agent_studio_api.auth.dependencies import auth_service
from universal_agent_studio_api.auth.models import BootstrapOwnerRequest
from universal_agent_studio_api.auth.service import AuthService
from universal_agent_studio_api.settings import Settings

router = APIRouter(prefix="/api/v1/bootstrap", tags=["bootstrap"])


def _set_session_cookie(
    response: Response,
    token: str,
    settings: Settings,
) -> None:
    response.set_cookie(
        "uas_session",
        token,
        max_age=settings.session_ttl_seconds,
        httponly=True,
        secure=settings.secure_cookies,
        samesite="lax",
        path="/",
    )


@router.get("/status")
async def bootstrap_status(
    service: Annotated[AuthService, Depends(auth_service)],
) -> dict[str, bool]:
    return {"bootstrap_required": not await service.bootstrap_status()}


@router.post("/owner", status_code=status.HTTP_201_CREATED)
async def bootstrap_owner(
    body: BootstrapOwnerRequest,
    response: Response,
    service: Annotated[AuthService, Depends(auth_service)],
) -> dict[str, object]:
    material = await service.bootstrap(
        login_name=body.login_name,
        password=body.password.get_secret_value(),
        preferred_locale=body.preferred_locale,
    )
    _set_session_cookie(response, material.raw_session_token, service.settings)
    return {
        "owner": {
            "login_name": material.owner.login_name,
            "preferred_locale": material.owner.preferred_locale,
        },
        "csrf_token": material.raw_csrf_token,
    }
