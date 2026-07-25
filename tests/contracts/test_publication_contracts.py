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
