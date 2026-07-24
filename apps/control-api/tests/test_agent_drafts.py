import copy
import json
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from importlib.util import find_spec
from pathlib import Path
from typing import Any, cast
from uuid import uuid4

import pytest
import pytest_asyncio
from conftest import MemoryAgentVersionPersistence, MemoryAuthStore
from httpx import ASGITransport, AsyncClient
from universal_agent_kernel.contracts.canonical import content_digest
from universal_agent_platform_store.repositories.drafts import (
    DraftRevisionConflict,
)
from universal_agent_platform_store.scope import RequestScope
from universal_agent_studio_api.agents.draft_service import DraftService
from universal_agent_studio_api.agents.drafts import (
    DraftDiffRequest,
    DraftLayoutView,
    StoredAgentDraft,
    UpdateAgentDraftRequest,
)
from universal_agent_studio_api.errors import ApiError
from universal_agent_studio_api.main import create_app
from universal_agent_studio_api.settings import Settings

ROOT = Path(__file__).parents[3]
GOLDEN_AGENT = (
    ROOT
    / "contracts"
    / "examples"
    / "v0.1.0"
    / "valid"
    / "agent.calculator.ru-en.json"
)
SCOPE = RequestScope(
    workspace_id=uuid4(),
    project_id=uuid4(),
    owner_id=uuid4(),
)


def agent_spec() -> dict[str, Any]:
    return cast(
        dict[str, Any],
        json.loads(GOLDEN_AGENT.read_text(encoding="utf-8")),
    )


def layout(x: int = 0) -> DraftLayoutView:
    return DraftLayoutView.model_validate(
        {
            "nodes": [
                {"node_id": "user-input", "x": x, "y": 80},
                {"node_id": "planner-model", "x": 260, "y": 80},
                {"node_id": "calculator-tool", "x": 520, "y": 80},
                {"node_id": "structured-output", "x": 780, "y": 80},
            ],
            "viewport": {"x": 0, "y": 0, "zoom": 1},
        }
    )


class MemoryDraftPersistence:
    def __init__(self) -> None:
        self.stored: StoredAgentDraft | None = None

    async def create(
        self,
        *,
        scope: RequestScope,
        agent_id: str,
    ) -> tuple[StoredAgentDraft, bool]:
        if self.stored is not None:
            return self.stored, False
        spec = agent_spec()
        self.stored = StoredAgentDraft(
            id=uuid4(),
            agent_id=agent_id,
            revision=1,
            base_version_id=f"{agent_id}-v1",
            digest=content_digest(spec),
            agent_spec=spec,
            layout=layout().model_dump(),
            updated_at=datetime.now(UTC),
        )
        return self.stored, True

    async def get(
        self,
        *,
        scope: RequestScope,
        agent_id: str,
    ) -> StoredAgentDraft | None:
        if self.stored is None or self.stored.agent_id != agent_id:
            return None
        return self.stored

    async def update(
        self,
        *,
        scope: RequestScope,
        agent_id: str,
        expected_revision: int,
        agent_spec: dict[str, Any],
        digest: str,
        layout: dict[str, Any],
    ) -> StoredAgentDraft:
        if self.stored is None:
            raise RuntimeError("agent_draft_not_found")
        if self.stored.revision != expected_revision:
            raise DraftRevisionConflict("agent_draft_revision_conflict")
        self.stored = StoredAgentDraft(
            id=self.stored.id,
            agent_id=agent_id,
            revision=expected_revision + 1,
            base_version_id=self.stored.base_version_id,
            digest=digest,
            agent_spec=agent_spec,
            layout=layout,
            updated_at=datetime.now(UTC),
        )
        return self.stored


@pytest_asyncio.fixture
async def draft_client() -> AsyncIterator[AsyncClient]:
    app = create_app(
        auth_store=MemoryAuthStore(),
        agent_persistence=MemoryAgentVersionPersistence(),
        draft_persistence=MemoryDraftPersistence(),
        settings=Settings(
            allowed_hosts=["testserver"],
            allowed_origins=["http://testserver"],
            secure_cookies=False,
            max_request_bytes=1_048_576,
        ),
    )
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
        headers={"Origin": "http://testserver"},
    ) as client:
        bootstrap = await client.post(
            "/api/v1/bootstrap/owner",
            json={
                "login_name": "owner",
                "password": "correct horse battery staple",
                "preferred_locale": "en-US",
            },
        )
        assert bootstrap.status_code == 201
        client.headers["X-CSRF-Token"] = bootstrap.json()["csrf_token"]
        yield client

def test_agent_draft_service_module_is_available() -> None:
    assert (
        find_spec("universal_agent_studio_api.agents.draft_service")
        is not None
    )


def test_agent_draft_routes_are_registered() -> None:
    paths = set(create_app().openapi()["paths"])

    assert "/api/v1/agents/{agent_id}/draft" in paths
    assert "/api/v1/agents/{agent_id}/draft/diff" in paths


@pytest.mark.asyncio
async def test_layout_only_update_preserves_agent_digest() -> None:
    persistence = MemoryDraftPersistence()
    service = DraftService(persistence)
    created, _ = await service.create("calculator-agent", SCOPE)

    updated = await service.update(
        "calculator-agent",
        UpdateAgentDraftRequest(
            expected_revision=created.revision,
            agent_spec=created.agent_spec,
            layout=layout(24),
        ),
        SCOPE,
    )

    assert updated.revision == 2
    assert updated.digest == created.digest
    assert updated.layout.nodes[0].x == 24


@pytest.mark.asyncio
async def test_invalid_node_reference_has_a_stable_location_and_is_not_saved() -> None:
    persistence = MemoryDraftPersistence()
    service = DraftService(persistence)
    created, _ = await service.create("calculator-agent", SCOPE)
    invalid = copy.deepcopy(created.agent_spec)
    invalid["nodes"][1]["model_profile_ref"] = "missing-profile"

    with pytest.raises(ApiError) as captured:
        await service.update(
            "calculator-agent",
            UpdateAgentDraftRequest(
                expected_revision=1,
                agent_spec=invalid,
                layout=layout(),
            ),
            SCOPE,
        )

    validation = captured.value.document["details"]["validation"]
    issue = next(
        item
        for item in validation["issues"]
        if item["code"] == "dangling_model_profile_reference"
    )
    assert captured.value.status_code == 422
    assert issue["json_pointer"] == "/nodes/1/model_profile_ref"
    assert issue["node_id"] == "planner-model"
    assert persistence.stored is not None
    assert persistence.stored.revision == 1


@pytest.mark.asyncio
async def test_diff_preview_is_deterministic_and_non_mutating() -> None:
    persistence = MemoryDraftPersistence()
    service = DraftService(persistence)
    created, _ = await service.create("calculator-agent", SCOPE)
    candidate = copy.deepcopy(created.agent_spec)
    candidate["localized_metadata"]["name"]["en-US"] = "Math Agent"
    candidate["localized_metadata"]["name"]["ru-RU"] = "Математический агент"

    preview = await service.preview_diff(
        "calculator-agent",
        DraftDiffRequest(
            expected_revision=created.revision,
            candidate_agent_spec=candidate,
        ),
        SCOPE,
    )

    assert [item.json_pointer for item in preview.operations] == [
        "/localized_metadata/name/en-US",
        "/localized_metadata/name/ru-RU",
    ]
    assert all(item.op == "replace" for item in preview.operations)
    assert persistence.stored is not None
    assert persistence.stored.revision == 1
    assert persistence.stored.agent_spec != candidate


@pytest.mark.asyncio
async def test_http_create_update_diff_and_stale_conflict(
    draft_client: AsyncClient,
) -> None:
    created = await draft_client.post(
        "/api/v1/agents/calculator-agent/draft"
    )
    repeated = await draft_client.post(
        "/api/v1/agents/calculator-agent/draft"
    )
    created_document = created.json()
    changed_layout = copy.deepcopy(created_document["layout"])
    changed_layout["nodes"][0]["x"] = 24
    updated = await draft_client.put(
        "/api/v1/agents/calculator-agent/draft",
        json={
            "expected_revision": 1,
            "agent_spec": created_document["agent_spec"],
            "layout": changed_layout,
        },
    )
    candidate = copy.deepcopy(created_document["agent_spec"])
    candidate["localized_metadata"]["name"]["en-US"] = "Math Agent"
    preview = await draft_client.post(
        "/api/v1/agents/calculator-agent/draft/diff",
        json={
            "expected_revision": 2,
            "candidate_agent_spec": candidate,
        },
    )
    stale = await draft_client.put(
        "/api/v1/agents/calculator-agent/draft",
        json={
            "expected_revision": 1,
            "agent_spec": candidate,
            "layout": changed_layout,
        },
    )

    assert created.status_code == 201
    assert repeated.status_code == 200
    assert repeated.json()["revision"] == 1
    assert updated.status_code == 200
    assert updated.json()["revision"] == 2
    assert updated.json()["digest"] == created_document["digest"]
    assert preview.status_code == 200
    assert preview.json()["operations"][0]["json_pointer"] == (
        "/localized_metadata/name/en-US"
    )
    assert stale.status_code == 409
    assert stale.json()["code"] == "agent_draft_revision_conflict"


@pytest.mark.asyncio
async def test_secret_candidate_is_rejected_without_echoing_value(
    draft_client: AsyncClient,
) -> None:
    created = await draft_client.post(
        "/api/v1/agents/calculator-agent/draft"
    )
    candidate = copy.deepcopy(created.json()["agent_spec"])
    candidate["nodes"][0]["config"]["api_key"] = "must-not-be-returned"

    response = await draft_client.post(
        "/api/v1/agents/calculator-agent/draft/diff",
        json={
            "expected_revision": 1,
            "candidate_agent_spec": candidate,
        },
    )

    assert response.status_code == 422
    assert response.json()["code"] == "agent_spec_invalid"
    assert "must-not-be-returned" not in response.text


@pytest.mark.asyncio
async def test_draft_write_requires_csrf(
    draft_client: AsyncClient,
) -> None:
    del draft_client.headers["X-CSRF-Token"]

    response = await draft_client.post(
        "/api/v1/agents/calculator-agent/draft"
    )

    assert response.status_code == 403
    assert response.json()["code"] == "csrf_validation_failed"
