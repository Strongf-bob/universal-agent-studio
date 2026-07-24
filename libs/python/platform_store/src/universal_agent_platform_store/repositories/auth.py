"""Scoped owner and opaque-session persistence primitives."""

from __future__ import annotations

from datetime import datetime
from typing import cast
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from universal_agent_platform_store.models import Owner, Session, utc_now
from universal_agent_platform_store.repositories.base import ScopedRepository
from universal_agent_platform_store.scope import RequestScope


class AuthRepository(ScopedRepository):
    def __init__(
        self,
        session: AsyncSession,
        scope: RequestScope | None,
    ) -> None:
        super().__init__(session, scope)
        if self.scope.is_administrative:
            self.workspace_id = None
            self.project_id = None
        else:
            self.workspace_id, self.project_id = self.scope.tenant_ids()

    async def owner_by_login(self, login_name: str) -> Owner | None:
        workspace_id, project_id = self.scope.tenant_ids()
        return cast(
            Owner | None,
            await self.session.scalar(
                select(Owner).where(
                    Owner.workspace_id == workspace_id,
                    Owner.project_id == project_id,
                    Owner.login_name == login_name,
                ),
            ),
        )

    async def create_session(
        self,
        *,
        owner_id: UUID,
        token_hash: str,
        csrf_token_hash: str,
        expires_at: datetime,
    ) -> Session:
        workspace_id, project_id = self.scope.tenant_ids()
        session = Session(
            id=uuid4(),
            workspace_id=workspace_id,
            project_id=project_id,
            owner_id=owner_id,
            token_hash=token_hash,
            csrf_token_hash=csrf_token_hash,
            expires_at=expires_at,
        )
        self.session.add(session)
        await self.session.flush()
        return session

    async def session_by_token_hash(self, token_hash: str) -> Session | None:
        workspace_id, project_id = self.scope.tenant_ids()
        return cast(
            Session | None,
            await self.session.scalar(
                select(Session).where(
                    Session.workspace_id == workspace_id,
                    Session.project_id == project_id,
                    Session.token_hash == token_hash,
                    Session.revoked_at.is_(None),
                    Session.expires_at > utc_now(),
                ),
            ),
        )

    async def revoke_session(self, session_id: UUID) -> None:
        workspace_id, project_id = self.scope.tenant_ids()
        session = await self.session.scalar(
            select(Session).where(
                Session.id == session_id,
                Session.workspace_id == workspace_id,
                Session.project_id == project_id,
            )
        )
        if session is not None and session.revoked_at is None:
            session.revoked_at = utc_now()
            await self.session.flush()
