from typing import Annotated

from fastapi import APIRouter, Depends, Response, status

from universal_agent_studio_api.api.session import _clear_session_cookie
from universal_agent_studio_api.auth.dependencies import (
    auth_service,
    csrf_authenticated_owner,
)
from universal_agent_studio_api.auth.models import (
    AuthenticatedOwner,
    DeleteWorkspaceRequest,
)
from universal_agent_studio_api.auth.service import AuthService

router = APIRouter(prefix="/api/v1/workspace", tags=["workspace"])


@router.delete("", status_code=status.HTTP_204_NO_CONTENT)
async def delete_workspace(
    body: DeleteWorkspaceRequest,
    response: Response,
    authenticated: Annotated[
        AuthenticatedOwner,
        Depends(csrf_authenticated_owner),
    ],
    service: Annotated[AuthService, Depends(auth_service)],
) -> None:
    await service.delete_workspace(
        authenticated,
        current_password=body.current_password.get_secret_value(),
        confirmation=body.confirmation,
    )
    _clear_session_cookie(response, service)
