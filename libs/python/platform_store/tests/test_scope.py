from __future__ import annotations

from uuid import uuid4

import pytest
from universal_agent_platform_store.repositories.agents import AgentRepository
from universal_agent_platform_store.repositories.auth import AuthRepository
from universal_agent_platform_store.repositories.runs import RunRepository
from universal_agent_platform_store.scope import MissingScopeError, RequestScope


def test_all_protected_repositories_require_scope() -> None:
    for repository in (AgentRepository, AuthRepository, RunRepository):
        with pytest.raises(MissingScopeError):
            repository(session=object(), scope=None)  # type: ignore[arg-type]


def test_tenant_scope_requires_both_workspace_and_project() -> None:
    workspace_id = uuid4()

    with pytest.raises(MissingScopeError):
        RequestScope(workspace_id=workspace_id, project_id=None)


def test_explicit_administrative_scope_is_distinct() -> None:
    scope = RequestScope.administrative(reason="workspace bootstrap")

    assert scope.is_administrative is True
    assert scope.reason == "workspace bootstrap"
