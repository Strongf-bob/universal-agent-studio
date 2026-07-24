"""AgentVersion API values and persistence protocol."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol
from uuid import UUID

from pydantic import BaseModel, ConfigDict
from universal_agent_platform_store.scope import RequestScope


class ValidationIssueView(BaseModel):
    code: str
    json_pointer: str
    node_id: str | None
    message_key: str


class ValidationView(BaseModel):
    valid: bool
    issues: list[ValidationIssueView]


class AgentVersionImportView(BaseModel):
    version_id: str
    agent_id: str
    schema_version: str
    digest: str
    validation: ValidationView
    reused: bool


class AgentVersionView(BaseModel):
    version_id: str
    agent_id: str
    schema_version: str
    digest: str
    agent_spec: dict[str, Any]


class ActivateAgentVersionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    version_id: UUID
    expected_previous_version_id: UUID | None


class ActiveAgentVersionView(BaseModel):
    agent_id: str
    active_version_id: str


@dataclass(frozen=True)
class StoredAgentVersion:
    id: UUID
    agent_id: str
    schema_version: str
    digest: str
    agent_spec: dict[str, Any]


class AgentVersionPersistence(Protocol):
    async def import_version(
        self,
        *,
        scope: RequestScope,
        agent_spec: dict[str, Any],
        digest: str,
    ) -> tuple[StoredAgentVersion, bool]: ...

    async def get_version(
        self,
        *,
        scope: RequestScope,
        version_id: UUID,
    ) -> StoredAgentVersion | None: ...

    async def activate(
        self,
        *,
        scope: RequestScope,
        agent_id: str,
        version_id: UUID,
        expected_previous_version_id: UUID | None,
    ) -> UUID: ...
