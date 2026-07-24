"""AgentDraft API values and persistence protocol."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Literal, Protocol
from uuid import UUID

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    FiniteFloat,
    model_validator,
)
from universal_agent_platform_store.scope import RequestScope

from universal_agent_studio_api.agents.models import ValidationView

Identifier = str


class DraftNodePositionView(BaseModel):
    model_config = ConfigDict(extra="forbid")

    node_id: Identifier = Field(pattern=r"^[a-z][a-z0-9_-]{2,63}$")
    x: FiniteFloat = Field(ge=-100_000, le=100_000)
    y: FiniteFloat = Field(ge=-100_000, le=100_000)


class DraftViewportView(BaseModel):
    model_config = ConfigDict(extra="forbid")

    x: FiniteFloat = Field(ge=-100_000, le=100_000)
    y: FiniteFloat = Field(ge=-100_000, le=100_000)
    zoom: FiniteFloat = Field(ge=0.1, le=4)


class DraftLayoutView(BaseModel):
    model_config = ConfigDict(extra="forbid")

    nodes: list[DraftNodePositionView] = Field(max_length=256)
    viewport: DraftViewportView

    @model_validator(mode="after")
    def unique_node_ids(self) -> DraftLayoutView:
        node_ids = [node.node_id for node in self.nodes]
        if len(node_ids) != len(set(node_ids)):
            raise ValueError("duplicate_layout_node_id")
        return self


class AgentDraftView(BaseModel):
    schema_version: Literal["0.1.0"] = "0.1.0"
    draft_id: Identifier
    agent_id: Identifier
    revision: int
    base_version_id: Identifier
    digest: str
    agent_spec: dict[str, Any]
    layout: DraftLayoutView
    updated_at: datetime


class UpdateAgentDraftRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    expected_revision: int = Field(ge=1)
    agent_spec: dict[str, Any]
    layout: DraftLayoutView


class DraftDiffRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    expected_revision: int = Field(ge=1)
    candidate_agent_spec: dict[str, Any]


class DraftDiffOperationView(BaseModel):
    op: Literal["add", "remove", "replace"]
    json_pointer: str
    before: Any | None = None
    after: Any | None = None


class DraftDiffView(BaseModel):
    draft_id: Identifier
    revision: int
    candidate_digest: str
    validation: ValidationView
    operations: list[DraftDiffOperationView]


@dataclass(frozen=True)
class StoredAgentDraft:
    id: UUID
    agent_id: str
    revision: int
    base_version_id: str
    digest: str
    agent_spec: dict[str, Any]
    layout: dict[str, Any]
    updated_at: datetime

    @property
    def public_id(self) -> str:
        return f"{self.agent_id}-draft"


class AgentDraftPersistence(Protocol):
    async def create(
        self,
        *,
        scope: RequestScope,
        agent_id: str,
    ) -> tuple[StoredAgentDraft, bool]: ...

    async def get(
        self,
        *,
        scope: RequestScope,
        agent_id: str,
    ) -> StoredAgentDraft | None: ...

    async def update(
        self,
        *,
        scope: RequestScope,
        agent_id: str,
        expected_revision: int,
        agent_spec: dict[str, Any],
        digest: str,
        layout: dict[str, Any],
    ) -> StoredAgentDraft: ...
