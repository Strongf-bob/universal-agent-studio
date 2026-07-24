import copy
import json
from pathlib import Path
from typing import Any, cast

from jsonschema import Draft202012Validator
from referencing import Registry, Resource
from universal_agent_kernel.contracts.validation import validate_agent_spec

ROOT = Path(__file__).parents[2]
SCHEMA_DIR = ROOT / "contracts" / "schemas" / "v0.1.0"
EXAMPLE_DIR = ROOT / "contracts" / "examples" / "v0.1.0"


def load_json(path: Path) -> dict[str, Any]:
    return cast(dict[str, Any], json.loads(path.read_text(encoding="utf-8")))


def schema_registry() -> tuple[Registry, dict[str, dict[str, Any]]]:
    schemas = {
        path.name: load_json(path)
        for path in sorted(SCHEMA_DIR.glob("*.schema.json"))
    }
    registry = Registry().with_resources(
        (schema["$id"], Resource.from_contents(schema))
        for schema in schemas.values()
    )
    return registry, schemas


def validation_errors(instance: dict[str, Any], schema_name: str) -> list[Any]:
    registry, schemas = schema_registry()
    validator = Draft202012Validator(schemas[schema_name], registry=registry)
    return sorted(validator.iter_errors(instance), key=lambda error: list(error.path))


def test_golden_calculator_agent_matches_agentspec_schema() -> None:
    agent = load_json(EXAMPLE_DIR / "valid" / "agent.calculator.ru-en.json")

    assert validation_errors(agent, "agent-spec.schema.json") == []


def test_agentspec_requires_localized_metadata() -> None:
    agent = load_json(EXAMPLE_DIR / "valid" / "agent.calculator.ru-en.json")
    invalid_agent = copy.deepcopy(agent)
    del invalid_agent["localized_metadata"]

    errors = validation_errors(invalid_agent, "agent-spec.schema.json")

    assert any(error.validator == "required" for error in errors)


def test_agent_draft_contract_is_registered() -> None:
    assert (SCHEMA_DIR / "agent-draft.schema.json").is_file()


def test_dangling_model_reference_has_a_precise_node_location() -> None:
    agent = load_json(EXAMPLE_DIR / "valid" / "agent.calculator.ru-en.json")
    invalid_agent = copy.deepcopy(agent)
    invalid_agent["nodes"][1]["model_profile_ref"] = "missing-profile"

    issue = next(
        item
        for item in validate_agent_spec(invalid_agent).issues
        if item.code == "dangling_model_profile_reference"
    )

    assert issue.json_pointer == "/nodes/1/model_profile_ref"
    assert issue.node_id == "planner-model"
