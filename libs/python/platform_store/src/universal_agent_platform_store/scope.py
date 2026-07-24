"""Explicit tenant scope required by every protected repository."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID


class MissingScopeError(ValueError):
    pass


@dataclass(frozen=True)
class RequestScope:
    workspace_id: UUID | None
    project_id: UUID | None
    owner_id: UUID | None = None
    is_administrative: bool = False
    reason: str | None = None

    def __post_init__(self) -> None:
        has_tenant = self.workspace_id is not None and self.project_id is not None
        has_partial_tenant = (self.workspace_id is None) != (self.project_id is None)
        if has_partial_tenant:
            raise MissingScopeError("workspace_and_project_scope_required")
        if self.is_administrative:
            if has_tenant or not self.reason:
                raise MissingScopeError("invalid_administrative_scope")
        elif not has_tenant:
            raise MissingScopeError("workspace_and_project_scope_required")

    @classmethod
    def administrative(cls, *, reason: str) -> RequestScope:
        return cls(
            workspace_id=None,
            project_id=None,
            is_administrative=True,
            reason=reason,
        )

    def tenant_ids(self) -> tuple[UUID, UUID]:
        if self.workspace_id is None or self.project_id is None:
            raise MissingScopeError("tenant_scope_required")
        return self.workspace_id, self.project_id
