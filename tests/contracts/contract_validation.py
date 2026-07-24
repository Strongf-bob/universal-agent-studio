from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

from jsonschema import Draft202012Validator, FormatChecker
from referencing import Registry, Resource

FORBIDDEN_SECRET_KEYS = {
    "accesstoken",
    "apikey",
    "authorization",
    "authtoken",
    "bearer",
    "bearertoken",
    "clientsecret",
    "password",
    "passphrase",
    "privatekey",
    "refreshtoken",
    "secret",
    "secretkey",
    "sessiontoken",
    "token",
}
TERMINAL_EVENT_TYPES = {
    "run.cancelled",
    "run.completed",
    "run.failed",
}


@dataclass(frozen=True)
class ContractCase:
    path: str
    schema: str
    valid: bool
    expected_error_code: str | None = None

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> ContractCase:
        return cls(
            path=value["path"],
            schema=value["schema"],
            valid=value["valid"],
            expected_error_code=value.get("expected_error_code"),
        )


def load_json(path: Path) -> dict[str, Any]:
    return cast(dict[str, Any], json.loads(path.read_text(encoding="utf-8")))


def load_schema_registry(root: Path) -> tuple[Registry, dict[str, dict[str, Any]]]:
    schema_dir = root / "contracts" / "schemas" / "v0.1.0"
    schemas = {
        path.name: load_json(path)
        for path in sorted(schema_dir.glob("*.schema.json"))
    }
    registry = Registry().with_resources(
        (schema["$id"], Resource.from_contents(schema))
        for schema in schemas.values()
    )
    return registry, schemas


def validate_fixture(case: ContractCase, root: Path) -> list[str]:
    instance = load_json(
        root / "contracts" / "examples" / "v0.1.0" / case.path
    )
    registry, schemas = load_schema_registry(root)
    validator = Draft202012Validator(
        schemas[case.schema],
        registry=registry,
        format_checker=FormatChecker(),
    )

    errors: set[str] = set()
    if list(validator.iter_errors(instance)):
        errors.add("schema_validation_failed")

    errors.update(find_forbidden_secret_keys(instance))

    if case.schema == "agent-spec.schema.json":
        errors.update(validate_agent_graph(instance))
    elif case.schema == "run-trace.schema.json":
        errors.update(validate_run_trace(instance))

    return sorted(errors)


def find_forbidden_secret_keys(value: Any) -> set[str]:
    errors: set[str] = set()

    if isinstance(value, dict):
        for key, child in value.items():
            snake_key = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", key)
            normalized_key = re.sub(r"[^a-z0-9]", "", snake_key.lower())
            if normalized_key in FORBIDDEN_SECRET_KEYS:
                errors.add("secret_key_forbidden")
            errors.update(find_forbidden_secret_keys(child))
    elif isinstance(value, list):
        for child in value:
            errors.update(find_forbidden_secret_keys(child))

    return errors


def validate_agent_graph(agent: dict[str, Any]) -> set[str]:
    errors: set[str] = set()
    nodes = agent.get("nodes", [])
    node_ids = [node.get("id") for node in nodes]

    if len(node_ids) != len(set(node_ids)):
        errors.add("duplicate_node_id")

    edge_ids = [edge.get("id") for edge in agent.get("edges", [])]
    if len(edge_ids) != len(set(edge_ids)):
        errors.add("duplicate_edge_id")

    model_profile_ids = {
        profile.get("id") for profile in agent.get("model_profiles", [])
    }
    tool_ids = {tool.get("id") for tool in agent.get("tools", [])}
    nodes_by_id = {node.get("id"): node for node in nodes}

    for node in nodes:
        input_port_ids = [port.get("id") for port in node.get("input_ports", [])]
        output_port_ids = [port.get("id") for port in node.get("output_ports", [])]
        if len(input_port_ids) != len(set(input_port_ids)):
            errors.add("duplicate_port_id")
        if len(output_port_ids) != len(set(output_port_ids)):
            errors.add("duplicate_port_id")

        model_ref = node.get("model_profile_ref")
        if model_ref is not None and model_ref not in model_profile_ids:
            errors.add("dangling_model_profile_reference")

        tool_ref = node.get("tool_ref")
        if tool_ref is not None and tool_ref not in tool_ids:
            errors.add("dangling_tool_reference")

    for edge in agent.get("edges", []):
        for endpoint_name, port_collection in (
            ("source", "output_ports"),
            ("target", "input_ports"),
        ):
            endpoint = edge.get(endpoint_name, {})
            node = nodes_by_id.get(endpoint.get("node_id"))
            if node is None:
                errors.add("dangling_node_reference")
                continue

            port_ids = {port.get("id") for port in node.get(port_collection, [])}
            if endpoint.get("port_id") not in port_ids:
                errors.add("dangling_port_reference")

    return errors


def validate_run_trace(trace: dict[str, Any]) -> set[str]:
    errors: set[str] = set()
    events = trace.get("events", [])

    sequences = [event.get("sequence") for event in events]
    if sequences != list(range(1, len(events) + 1)):
        errors.add("event_sequence_invalid")

    event_ids = [event.get("event_id") for event in events]
    if len(event_ids) != len(set(event_ids)):
        errors.add("duplicate_event_id")

    run_id = trace.get("run_id")
    if any(event.get("run_id") != run_id for event in events):
        errors.add("event_run_mismatch")

    if events:
        if events[0].get("type") != "run.started":
            errors.add("event_lifecycle_invalid")
        if events[-1].get("type") not in TERMINAL_EVENT_TYPES:
            errors.add("event_lifecycle_invalid")

        request_id = trace.get("request_id")
        if events[0].get("causation_id") != request_id:
            errors.add("event_causation_invalid")
        for previous, current in zip(events, events[1:], strict=False):
            if current.get("causation_id") != previous.get("event_id"):
                errors.add("event_causation_invalid")

    status = trace.get("status")
    expected_terminal_type = (
        {
            "cancelled": "run.cancelled",
            "completed": "run.completed",
            "failed": "run.failed",
        }.get(status)
        if isinstance(status, str)
        else None
    )
    if events and events[-1].get("type") != expected_terminal_type:
        errors.add("event_lifecycle_invalid")

    redaction_policy_id = trace.get("provenance", {}).get("redaction_policy_id")
    if any(
        event.get("redaction_policy_id") != redaction_policy_id
        for event in events
    ):
        errors.add("redaction_policy_mismatch")

    return errors
