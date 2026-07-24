from __future__ import annotations

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from universal_agent_platform_store.scope import MissingScopeError, RequestScope


class ScopedRepository:
    def __init__(
        self,
        session: AsyncSession,
        scope: RequestScope | None,
    ) -> None:
        if scope is None:
            raise MissingScopeError("repository_scope_required")
        self.session = session
        self.scope = scope

    def tenant_ids(self) -> tuple[UUID, UUID]:
        return self.scope.tenant_ids()
