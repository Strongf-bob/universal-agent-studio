from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from httpx import AsyncClient

ROOT = Path(__file__).parents[3]
GOLDEN_AGENT = (
    ROOT
    / "contracts"
    / "examples"
    / "v0.1.0"
    / "valid"
    / "agent.calculator.ru-en.json"
)
LOCKED_DIGEST = (
    ROOT / "tests" / "fixtures" / "canonical" / "agent.calculator.sha256"
).read_text(encoding="utf-8").strip()


def _headers(csrf_token: str) -> dict[str, str]:
    return {
        "Content-Type": "application/json",
        "X-CSRF-Token": csrf_token,
    }


async def _import(
    client: AsyncClient,
    csrf_token: str,
    document: dict[str, Any],
) -> Any:
    return await client.post(
        "/api/v1/agent-versions/import",
        content=json.dumps(document).encode(),
        headers=_headers(csrf_token),
    )


@pytest.mark.asyncio
async def test_golden_import_is_digest_locked_and_idempotent(
    client: AsyncClient,
    bootstrapped_session: tuple[str, str],
) -> None:
    _, csrf_token = bootstrapped_session
    raw = GOLDEN_AGENT.read_bytes()

    first = await client.post(
        "/api/v1/agent-versions/import",
        content=raw,
        headers=_headers(csrf_token),
    )
    second = await client.post(
        "/api/v1/agent-versions/import",
        content=raw,
        headers=_headers(csrf_token),
    )

    assert first.status_code == 201
    assert first.json() == {
        "version_id": first.json()["version_id"],
        "agent_id": "calculator-agent",
        "schema_version": "0.1.0",
        "digest": LOCKED_DIGEST,
        "validation": {"valid": True, "issues": []},
        "reused": False,
    }
    assert second.status_code == 200
    assert second.json()["version_id"] == first.json()["version_id"]
    assert second.json()["digest"] == LOCKED_DIGEST
    assert second.json()["reused"] is True

    fetched = await client.get(
        f"/api/v1/agent-versions/{first.json()['version_id']}"
    )
    assert fetched.status_code == 200
    assert fetched.json()["agent_spec"] == json.loads(raw)
    assert fetched.json()["digest"] == LOCKED_DIGEST


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("mutator", "expected_code"),
    [
        (lambda value: value.pop("interface"), "schema_validation_failed"),
        (
            lambda value: value["edges"][0]["target"].update(
                {"node_id": "missing-node"}
            ),
            "dangling_node_reference",
        ),
        (
            lambda value: value["nodes"][0]["config"].update(
                {"api_key": "must-not-be-stored"}
            ),
            "secret_key_forbidden",
        ),
    ],
)
async def test_invalid_agent_spec_returns_stable_validation_issues(
    client: AsyncClient,
    bootstrapped_session: tuple[str, str],
    mutator: Any,
    expected_code: str,
) -> None:
    _, csrf_token = bootstrapped_session
    document = json.loads(GOLDEN_AGENT.read_bytes())
    mutator(document)

    response = await _import(client, csrf_token, document)

    assert response.status_code == 422
    assert response.json()["code"] == "agent_spec_invalid"
    assert expected_code in {
        issue["code"] for issue in response.json()["details"]["validation"]["issues"]
    }


@pytest.mark.asyncio
async def test_duplicate_json_keys_are_rejected_before_binding(
    client: AsyncClient,
    bootstrapped_session: tuple[str, str],
) -> None:
    _, csrf_token = bootstrapped_session
    raw = GOLDEN_AGENT.read_text(encoding="utf-8").replace(
        '"schema_version": "0.1.0",',
        '"schema_version": "0.1.0", "schema_version": "0.1.0",',
        1,
    )

    response = await client.post(
        "/api/v1/agent-versions/import",
        content=raw,
        headers=_headers(csrf_token),
    )

    assert response.status_code == 422
    assert response.json()["code"] == "duplicate_json_key"
    assert response.json()["details"] == {}


@pytest.mark.asyncio
async def test_oversized_agent_spec_is_rejected(
    client: AsyncClient,
    bootstrapped_session: tuple[str, str],
) -> None:
    _, csrf_token = bootstrapped_session

    response = await client.post(
        "/api/v1/agent-versions/import",
        content=b"{" + (b" " * 20_000) + b"}",
        headers=_headers(csrf_token),
    )

    assert response.status_code == 413
    assert response.json()["code"] == "request_too_large"


@pytest.mark.asyncio
async def test_activation_requires_the_expected_previous_version(
    client: AsyncClient,
    bootstrapped_session: tuple[str, str],
) -> None:
    _, csrf_token = bootstrapped_session
    first_document = json.loads(GOLDEN_AGENT.read_bytes())
    second_document = {**first_document, "revision": 2}
    first = await _import(client, csrf_token, first_document)
    second = await _import(client, csrf_token, second_document)

    activated = await client.post(
        "/api/v1/agents/calculator-agent/active-version",
        json={
            "version_id": first.json()["version_id"],
            "expected_previous_version_id": None,
        },
        headers={"X-CSRF-Token": csrf_token},
    )
    conflict = await client.post(
        "/api/v1/agents/calculator-agent/active-version",
        json={
            "version_id": second.json()["version_id"],
            "expected_previous_version_id": None,
        },
        headers={"X-CSRF-Token": csrf_token},
    )
    changed = await client.post(
        "/api/v1/agents/calculator-agent/active-version",
        json={
            "version_id": second.json()["version_id"],
            "expected_previous_version_id": first.json()["version_id"],
        },
        headers={"X-CSRF-Token": csrf_token},
    )
    fetched = await client.get(
        "/api/v1/agents/calculator-agent/active-version"
    )

    assert activated.status_code == 200
    assert activated.json()["active_version_id"] == first.json()["version_id"]
    assert conflict.status_code == 409
    assert conflict.json()["code"] == "active_version_changed"
    assert changed.status_code == 200
    assert changed.json()["active_version_id"] == second.json()["version_id"]
    assert fetched.status_code == 200
    assert fetched.json()["version_id"] == second.json()["version_id"]
    assert fetched.json()["digest"] == second.json()["digest"]
    assert fetched.json()["agent_spec"] == second_document
