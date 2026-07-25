from __future__ import annotations

import json
from pathlib import Path

from jsonschema import Draft202012Validator
from referencing import Registry, Resource

ROOT = Path(__file__).parents[2]
SCHEMA_DIR = ROOT / "contracts" / "schemas" / "v0.1.0"
EXAMPLE_DIR = ROOT / "contracts" / "examples" / "v0.1.0"


def _load(path: Path) -> dict[str, object]:
    value = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(value, dict)
    return value


def _validate(schema_name: str, document: dict[str, object]) -> list[object]:
    schemas = {
        path.name: _load(path)
        for path in sorted(SCHEMA_DIR.glob("*.schema.json"))
    }
    registry = Registry().with_resources(
        (str(schema["$id"]), Resource.from_contents(schema))
        for schema in schemas.values()
    )
    return list(
        Draft202012Validator(
            schemas[schema_name],
            registry=registry,
        ).iter_errors(document)
    )


def _validate_definition(
    schema_name: str,
    definition: str,
    document: dict[str, object],
) -> list[object]:
    schemas = {
        path.name: _load(path)
        for path in sorted(SCHEMA_DIR.glob("*.schema.json"))
    }
    registry = Registry().with_resources(
        (str(schema["$id"]), Resource.from_contents(schema))
        for schema in schemas.values()
    )
    schema_id = str(schemas[schema_name]["$id"])
    return list(
        Draft202012Validator(
            {"$ref": f"{schema_id}#/$defs/{definition}"},
            registry=registry,
        ).iter_errors(document)
    )


def test_public_agent_example_is_valid_and_sanitized() -> None:
    document = _load(EXAMPLE_DIR / "valid" / "public-agent.calculator.json")

    assert _validate("public-agent.schema.json", document) == []
    serialized = json.dumps(document, sort_keys=True)
    for forbidden in (
        "prompt",
        "tools",
        "model_profile",
        "agent_spec",
        "trace_id",
        "durable_execution_id",
    ):
        assert forbidden not in serialized


def test_public_run_example_is_valid_and_sanitized() -> None:
    document = _load(EXAMPLE_DIR / "valid" / "public-run.completed.json")

    assert _validate("public-run.schema.json", document) == []
    assert "run_capability" not in document
    assert "durable_execution_id" not in document


def test_publication_contract_models_are_generated() -> None:
    from universal_agent_kernel.contracts import generated

    expected_models = {
        "ApiKeyCreateRequest",
        "ApiKeyCreateView",
        "PublicationState",
        "PublishRequest",
        "PublicAgentView",
        "PublicRunCreateRequest",
        "PublicRunView",
        "RollbackRequest",
        "WebhookCreateRequest",
        "WebhookCreateView",
    }

    assert expected_models <= set(dir(generated))


def test_public_event_contract_has_sanitized_progress_type() -> None:
    from universal_agent_kernel.contracts.generated import PublicRunEvent

    event = PublicRunEvent.model_validate(
        {
            "schema_version": "0.1.0",
            "sequence": 2,
            "type": "run.progress",
            "status": "running",
            "output": None,
            "error_code": None,
            "occurred_at": "2026-07-25T12:00:00Z",
        }
    )

    assert event.type.value == "run.progress"


def test_one_time_secret_views_are_strict_and_satisfiable() -> None:
    api_key: dict[str, object] = {
        "key_id": "11111111-1111-4111-8111-111111111111",
        "label": "CLI",
        "prefix": "0123456789abcdef",
        "scopes": ["runs:create"],
        "expires_at": None,
        "created_at": "2026-07-25T12:00:00Z",
        "last_used_at": None,
        "revoked_at": None,
        "secret": f"uas_live_0123456789abcdef_{'A' * 43}",
    }
    webhook: dict[str, object] = {
        "subscription_id": "22222222-2222-4222-8222-222222222222",
        "label": "Terminal",
        "target_url": "https://hooks.example.test/terminal",
        "events": ["run.completed"],
        "created_at": "2026-07-25T12:00:00Z",
        "revoked_at": None,
        "secret": f"whsec_{'A' * 43}",
    }

    assert (
        _validate_definition(
            "publication.schema.json",
            "ApiKeyCreateView",
            api_key,
        )
        == []
    )
    assert (
        _validate_definition(
            "publication.schema.json",
            "WebhookCreateView",
            webhook,
        )
        == []
    )
    api_key["unexpected"] = True
    assert _validate_definition(
        "publication.schema.json",
        "ApiKeyCreateView",
        api_key,
    )
