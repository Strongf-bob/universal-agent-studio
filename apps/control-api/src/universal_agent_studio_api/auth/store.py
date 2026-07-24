"""PostgreSQL AuthStore implementation with explicit administrative operations."""

from __future__ import annotations

from datetime import datetime
from typing import cast
from uuid import UUID, uuid4

from sqlalchemy import delete, select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from universal_agent_platform_store.models import (
    Owner,
    Project,
    Workspace,
)
from universal_agent_platform_store.models import (
    Session as DbSession,
)
from universal_agent_platform_store.scope import RequestScope

from universal_agent_studio_api.auth.models import (
    OwnerIdentity,
    SessionIdentity,
)


def _owner_identity(owner: Owner) -> OwnerIdentity:
    return OwnerIdentity(
        id=owner.id,
        workspace_id=owner.workspace_id,
        project_id=owner.project_id,
        login_name=owner.login_name,
        password_hash=owner.password_hash,
        preferred_locale=owner.preferred_locale,
    )


def _session_identity(session: DbSession) -> SessionIdentity:
    return SessionIdentity(
        id=session.id,
        workspace_id=session.workspace_id,
        project_id=session.project_id,
        owner_id=session.owner_id,
        token_hash=session.token_hash,
        csrf_token_hash=session.csrf_token_hash,
        expires_at=session.expires_at,
        revoked_at=session.revoked_at,
    )


class SqlAuthStore:
    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
    ) -> None:
        self.session_factory = session_factory
        self.administrative_scope = RequestScope.administrative(
            reason="local owner authentication boundary"
        )

    async def bootstrap_status(self) -> bool:
        async with self.session_factory() as session:
            owner_id = await session.scalar(select(Owner.id).limit(1))
            return owner_id is not None

    async def bootstrap_owner(
        self,
        *,
        login_name: str,
        password_hash: str,
        preferred_locale: str,
    ) -> OwnerIdentity | None:
        async with self.session_factory() as session, session.begin():
            await session.execute(text("SELECT pg_advisory_xact_lock(883013557)"))
            if await session.scalar(select(Owner.id).limit(1)) is not None:
                return None

            workspace = Workspace(
                id=uuid4(),
                slug="local",
                name="Local workspace",
            )
            session.add(workspace)
            await session.flush()
            project = Project(
                id=uuid4(),
                workspace_id=workspace.id,
                slug="default",
                name="Default project",
            )
            session.add(project)
            await session.flush()
            owner = Owner(
                id=uuid4(),
                workspace_id=workspace.id,
                project_id=project.id,
                login_name=login_name,
                password_hash=password_hash,
                preferred_locale=preferred_locale,
            )
            session.add(owner)
            await session.flush()
            return _owner_identity(owner)

    async def owner_by_login(self, login_name: str) -> OwnerIdentity | None:
        async with self.session_factory() as session:
            owner = await session.scalar(
                select(Owner).where(Owner.login_name == login_name).limit(1)
            )
            return _owner_identity(owner) if owner is not None else None

    async def create_session(
        self,
        *,
        owner: OwnerIdentity,
        token_hash: str,
        csrf_token_hash: str,
        expires_at: datetime,
    ) -> SessionIdentity:
        async with self.session_factory() as session, session.begin():
            record = DbSession(
                id=uuid4(),
                workspace_id=owner.workspace_id,
                project_id=owner.project_id,
                owner_id=owner.id,
                token_hash=token_hash,
                csrf_token_hash=csrf_token_hash,
                expires_at=expires_at,
            )
            session.add(record)
            await session.flush()
            return _session_identity(record)

    async def session_with_owner(
        self,
        token_hash: str,
    ) -> tuple[SessionIdentity, OwnerIdentity] | None:
        async with self.session_factory() as session:
            row = (
                await session.execute(
                    select(DbSession, Owner)
                    .join(Owner, Owner.id == DbSession.owner_id)
                    .where(DbSession.token_hash == token_hash)
                )
            ).one_or_none()
            if row is None:
                return None
            session_record, owner = cast(tuple[DbSession, Owner], row)
            return _session_identity(session_record), _owner_identity(owner)

    async def update_session_csrf(
        self,
        session_id: UUID,
        csrf_token_hash: str,
    ) -> SessionIdentity:
        async with self.session_factory() as session, session.begin():
            record = await session.scalar(
                select(DbSession).where(DbSession.id == session_id).with_for_update()
            )
            if record is None:
                raise RuntimeError("session_not_found")
            record.csrf_token_hash = csrf_token_hash
            await session.flush()
            return _session_identity(record)

    async def revoke_session(
        self,
        session_id: UUID,
        revoked_at: datetime,
    ) -> None:
        async with self.session_factory() as session, session.begin():
            record = await session.scalar(
                select(DbSession).where(DbSession.id == session_id).with_for_update()
            )
            if record is not None and record.revoked_at is None:
                record.revoked_at = revoked_at

    async def delete_workspace(self, workspace_id: UUID) -> None:
        async with self.session_factory() as session, session.begin():
            await session.execute(delete(Workspace).where(Workspace.id == workspace_id))
