"""Schema and semantic validation at AgentSpec trust boundaries."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from importlib import resources
from typing import Any, cast

from jsonschema import Draft202012Validator, FormatChecker

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
SCHEMA_DEFINITION_BY_FILE = {
    "agent-spec.schema.json": "AgentSpec",
    "agent-version.schema.json": "AgentVersion",
    "error-envelope.schema.json": "ErrorEnvelope",
    "interface-schema.schema.json": "InterfaceSchema",
    "model-profile.schema.json": "ModelProfile",
    "node-spec.schema.json": "NodeSpec",
    "run-event.schema.json": "RunEvent",
    "run-request.schema.json": "RunRequest",
    "run-trace.schema.json": "RunTrace",
    "tool-manifest.schema.json": "ToolManifest",
}


@dataclass(frozen=True)
class ValidationIssue:
    code: str
    json_pointer: str
    node_id: str | None
    message_key: str


@dataclass(frozen=True)
class ValidationResult:
    valid: bool
    issues: tuple[ValidationIssue, ...]


def _load_bundle() -> dict[str, Any]:
    bundle = (
        resources.files("universal_agent_kernel.contracts.schemas")
        .joinpath("bundle.schema.json")
        .read_text(encoding="utf-8")
    )
    return cast(dict[str, Any], json.loads(bundle))


def load_contract_schemas() -> dict[str, dict[str, Any]]:
    bundle = _load_bundle()
    definitions = cast(dict[str, dict[str, Any]], bundle["$defs"])
    return {
        filename: definitions[definition]
        for filename, definition in SCHEMA_DEFINITION_BY_FILE.items()
    }


def _json_pointer(path: list[Any]) -> str:
    if not path:
        return ""
    encoded = [
        str(part).replace("~", "~0").replace("/", "~1")
        for part in path
    ]
    return "/" + "/".join(encoded)


def _node_id(document: dict[str, Any], path: list[Any]) -> str | None:
    if len(path) < 2 or path[0] != "nodes" or not isinstance(path[1], int):
        return None
    nodes = document.get("nodes")
    if not isinstance(nodes, list) or path[1] >= len(nodes):
        return None
    node = nodes[path[1]]
    if not isinstance(node, dict):
        return None
    identifier = node.get("id")
    return identifier if isinstance(identifier, str) else None


def _schema_issues(
    document: dict[str, Any],
    schema_name: str,
) -> list[ValidationIssue]:
    bundle = _load_bundle()
    definition = SCHEMA_DEFINITION_BY_FILE[schema_name]
    schema = {"$ref": f"#/$defs/{definition}", "$defs": bundle["$defs"]}
    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    issues: list[ValidationIssue] = []
    for error in validator.iter_errors(document):
        path = list(error.absolute_path)
        issues.append(
            ValidationIssue(
                code="schema_validation_failed",
                json_pointer=_json_pointer(path),
                node_id=_node_id(document, path),
                message_key=f"validation.schema.{error.validator}",
            )
        )
    return issues


def validate_agent_input(
    agent_spec: dict[str, Any],
    input_document: dict[str, Any],
) -> ValidationResult:
    """Validate a run input against the active AgentSpec form interface."""
    interface = cast(dict[str, Any], agent_spec["interface"])
    fields = cast(list[dict[str, Any]], interface["input_fields"])
    schema = {
        "type": "object",
        "properties": {
            str(field["id"]): cast(dict[str, Any], field["schema"])
            for field in fields
        },
        "required": [
            str(field["id"])
            for field in fields
            if field.get("required") is True
        ],
        "additionalProperties": False,
    }
    issues = tuple(
        ValidationIssue(
            code="input_validation_failed",
            json_pointer=_json_pointer(list(error.absolute_path)),
            node_id=None,
            message_key=f"validation.input.{error.validator}",
        )
        for error in Draft202012Validator(schema).iter_errors(input_document)
    )
    return ValidationResult(valid=not issues, issues=issues)


def find_forbidden_secret_keys(value: Any) -> set[str]:
    errors: set[str] = set()

    if isinstance(value, dict):
        for key, child in value.items():
            snake_key = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", str(key))
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


def validate_agent_spec(document: dict[str, Any]) -> ValidationResult:
    issues = _schema_issues(document, "agent-spec.schema.json")
    semantic_codes = find_forbidden_secret_keys(document) | validate_agent_graph(
        document
    )
    issues.extend(
        ValidationIssue(
            code=code,
            json_pointer="",
            node_id=None,
            message_key=f"validation.semantic.{code}",
        )
        for code in semantic_codes
    )
    ordered = tuple(
        sorted(
            issues,
            key=lambda issue: (
                issue.json_pointer,
                issue.code,
                issue.node_id or "",
                issue.message_key,
            ),
        )
    )
    return ValidationResult(valid=not ordered, issues=ordered)


def validation_codes(document: dict[str, Any], schema_name: str) -> list[str]:
    codes = {issue.code for issue in _schema_issues(document, schema_name)}
    codes.update(find_forbidden_secret_keys(document))
    if schema_name == "agent-spec.schema.json":
        codes.update(validate_agent_graph(document))
    elif schema_name == "run-trace.schema.json":
        codes.update(validate_run_trace(document))
    return sorted(codes)
