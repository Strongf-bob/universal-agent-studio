from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import datetime
from uuid import UUID, uuid4

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from universal_agent_studio_api.auth.models import OwnerIdentity, SessionIdentity
from universal_agent_studio_api.main import create_app
from universal_agent_studio_api.settings import Settings


class MemoryAuthStore:
    def __init__(self) -> None:
        self.owner: OwnerIdentity | None = None
        self.sessions: dict[UUID, SessionIdentity] = {}
        self.deleted_workspace_id: UUID | None = None

    async def bootstrap_status(self) -> bool:
        return self.owner is not None

    async def bootstrap_owner(
        self,
        *,
        login_name: str,
        password_hash: str,
        preferred_locale: str,
    ) -> OwnerIdentity | None:
        if self.owner is not None:
            return None
        self.owner = OwnerIdentity(
            id=uuid4(),
            workspace_id=uuid4(),
            project_id=uuid4(),
            login_name=login_name,
            password_hash=password_hash,
            preferred_locale=preferred_locale,
        )
        return self.owner

    async def owner_by_login(self, login_name: str) -> OwnerIdentity | None:
        if self.owner is not None and self.owner.login_name == login_name:
            return self.owner
        return None

    async def create_session(
        self,
        *,
        owner: OwnerIdentity,
        token_hash: str,
        csrf_token_hash: str,
        expires_at: datetime,
    ) -> SessionIdentity:
        session = SessionIdentity(
            id=uuid4(),
            workspace_id=owner.workspace_id,
            project_id=owner.project_id,
            owner_id=owner.id,
            token_hash=token_hash,
            csrf_token_hash=csrf_token_hash,
            expires_at=expires_at,
            revoked_at=None,
        )
        self.sessions[session.id] = session
        return session

    async def session_with_owner(
        self,
        token_hash: str,
    ) -> tuple[SessionIdentity, OwnerIdentity] | None:
        for session in self.sessions.values():
            if (
                session.token_hash == token_hash
                and self.owner is not None
                and session.owner_id == self.owner.id
            ):
                return session, self.owner
        return None

    async def revoke_session(self, session_id: UUID, revoked_at: datetime) -> None:
        session = self.sessions[session_id]
        self.sessions[session_id] = SessionIdentity(
            **{
                **session.__dict__,
                "revoked_at": revoked_at,
            }
        )

    async def update_session_csrf(
        self,
        session_id: UUID,
        csrf_token_hash: str,
    ) -> SessionIdentity:
        session = self.sessions[session_id]
        updated = SessionIdentity(
            **{
                **session.__dict__,
                "csrf_token_hash": csrf_token_hash,
            }
        )
        self.sessions[session_id] = updated
        return updated

    async def delete_workspace(self, workspace_id: UUID) -> None:
        self.deleted_workspace_id = workspace_id
        self.owner = None
        self.sessions.clear()


@pytest.fixture
def auth_store() -> MemoryAuthStore:
    return MemoryAuthStore()


@pytest_asyncio.fixture
async def client(auth_store: MemoryAuthStore) -> AsyncIterator[AsyncClient]:
    app = create_app(
        auth_store=auth_store,
        settings=Settings(
            allowed_hosts=["testserver", "localhost"],
            allowed_origins=["http://testserver", "http://localhost:3000"],
            secure_cookies=False,
            max_request_bytes=16_384,
        ),
    )
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
        headers={"Origin": "http://testserver"},
    ) as test_client:
        yield test_client


@pytest_asyncio.fixture
async def bootstrapped_session(
    client: AsyncClient,
) -> tuple[str, str]:
    response = await client.post(
        "/api/v1/bootstrap/owner",
        json={
            "login_name": "owner",
            "password": "correct horse battery staple",
            "preferred_locale": "en-US",
        },
    )
    assert response.status_code == 201
    csrf_token = response.json()["csrf_token"]
    session_token = client.cookies.get("uas_session")
    assert session_token is not None
    return session_token, csrf_token
