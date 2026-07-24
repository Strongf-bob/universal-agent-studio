import json
from pathlib import Path
from typing import Any, cast

from jsonschema import Draft202012Validator
from referencing import Registry, Resource

ROOT = Path(__file__).parents[2]
SCHEMA_DIR = ROOT / "contracts" / "schemas" / "v0.1.0"
EXAMPLE_DIR = ROOT / "contracts" / "examples" / "v0.1.0"


def load_json(path: Path) -> dict[str, Any]:
    return cast(dict[str, Any], json.loads(path.read_text(encoding="utf-8")))


def validator_for(schema_name: str) -> Draft202012Validator:
    schemas = [
        load_json(path)
        for path in sorted(SCHEMA_DIR.glob("*.schema.json"))
    ]
    registry = Registry().with_resources(
        (schema["$id"], Resource.from_contents(schema))
        for schema in schemas
    )
    selected = next(schema for schema in schemas if schema["$id"].endswith(schema_name))
    return Draft202012Validator(selected, registry=registry)


def test_run_request_matches_schema() -> None:
    request = load_json(EXAMPLE_DIR / "valid" / "run.request.json")

    assert list(validator_for("run-request.schema.json").iter_errors(request)) == []


def test_completed_trace_matches_schema() -> None:
    trace = load_json(EXAMPLE_DIR / "valid" / "run.trace.completed.json")

    assert list(validator_for("run-trace.schema.json").iter_errors(trace)) == []


def test_run_event_sequence_starts_at_one() -> None:
    event = load_json(EXAMPLE_DIR / "invalid" / "run.event.sequence.json")

    errors = list(validator_for("run-event.schema.json").iter_errors(event))

    assert any(error.validator == "minimum" for error in errors)
