"""Auth API values and persistence protocol."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Annotated, Protocol
from uuid import UUID

from pydantic import BaseModel, Field, SecretStr

Password = Annotated[SecretStr, Field(min_length=12, max_length=128)]
LoginName = Annotated[
    str, Field(min_length=3, max_length=128, pattern=r"^[a-z0-9._-]+$")
]


class BootstrapOwnerRequest(BaseModel):
    login_name: LoginName
    password: Password
    preferred_locale: Annotated[str, Field(pattern=r"^(ru-RU|en-US)$")]


class LoginRequest(BaseModel):
    login_name: LoginName
    password: Annotated[SecretStr, Field(min_length=1, max_length=128)]


class DeleteWorkspaceRequest(BaseModel):
    current_password: Annotated[SecretStr, Field(min_length=1, max_length=128)]
    confirmation: Annotated[str, Field(max_length=64)]


@dataclass(frozen=True)
class OwnerIdentity:
    id: UUID
    workspace_id: UUID
    project_id: UUID
    login_name: str
    password_hash: str
    preferred_locale: str


@dataclass(frozen=True)
class SessionIdentity:
    id: UUID
    workspace_id: UUID
    project_id: UUID
    owner_id: UUID
    token_hash: str
    csrf_token_hash: str
    expires_at: datetime
    revoked_at: datetime | None


@dataclass(frozen=True)
class SessionMaterial:
    owner: OwnerIdentity
    session: SessionIdentity
    raw_session_token: str
    raw_csrf_token: str


@dataclass(frozen=True)
class AuthenticatedOwner:
    owner: OwnerIdentity
    session: SessionIdentity


class AuthStore(Protocol):
    async def bootstrap_status(self) -> bool: ...

    async def bootstrap_owner(
        self,
        *,
        login_name: str,
        password_hash: str,
        preferred_locale: str,
    ) -> OwnerIdentity | None: ...

    async def owner_by_login(self, login_name: str) -> OwnerIdentity | None: ...

    async def create_session(
        self,
        *,
        owner: OwnerIdentity,
        token_hash: str,
        csrf_token_hash: str,
        expires_at: datetime,
    ) -> SessionIdentity: ...

    async def session_with_owner(
        self,
        token_hash: str,
    ) -> tuple[SessionIdentity, OwnerIdentity] | None: ...

    async def update_session_csrf(
        self,
        session_id: UUID,
        csrf_token_hash: str,
    ) -> SessionIdentity: ...

    async def revoke_session(
        self,
        session_id: UUID,
        revoked_at: datetime,
    ) -> None: ...

    async def delete_workspace(self, workspace_id: UUID) -> None: ...
