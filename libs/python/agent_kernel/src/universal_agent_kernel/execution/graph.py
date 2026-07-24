"""Narrow, deterministic interpreter for the Slice 1 AgentSpec graph."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime
from typing import Any, cast

from jsonschema import Draft202012Validator, FormatChecker

from universal_agent_kernel.contracts.canonical import content_digest
from universal_agent_kernel.contracts.validation import validate_agent_spec
from universal_agent_kernel.domain import (
    ExecutionCommand,
    KernelExecutionError,
    ModelRequest,
    NodeExecution,
    RunOutcome,
    RunTrace,
)
from universal_agent_kernel.execution.events import EventRecorder
from universal_agent_kernel.ports import ExecutionPorts

SUPPORTED_PATH = ("input", "model", "tool", "output")


def _duration_ms(started_at: datetime, completed_at: datetime) -> int:
    return max(0, round((completed_at - started_at).total_seconds() * 1000))


def _validate_schema(
    value: Mapping[str, object],
    schema: Mapping[str, object],
    *,
    code: str,
    node_id: str,
) -> None:
    validator = Draft202012Validator(
        dict(schema),
        format_checker=FormatChecker(),
    )
    if next(validator.iter_errors(dict(value)), None) is not None:
        raise KernelExecutionError(code, node_id=node_id)


def _execution_path(agent: dict[str, Any]) -> list[dict[str, Any]]:
    nodes = cast(list[dict[str, Any]], agent["nodes"])
    edges = cast(list[dict[str, Any]], agent["edges"])
    by_id = {cast(str, node["id"]): node for node in nodes}
    next_by_id: dict[str, list[str]] = {node_id: [] for node_id in by_id}
    for edge in edges:
        source = cast(dict[str, Any], edge["source"])
        target = cast(dict[str, Any], edge["target"])
        next_by_id[cast(str, source["node_id"])].append(
            cast(str, target["node_id"])
        )

    input_nodes = [node for node in nodes if node["kind"] == "input"]
    if len(input_nodes) != 1:
        raise KernelExecutionError("unsupported_graph_shape")

    path: list[dict[str, Any]] = []
    visited: set[str] = set()
    current = input_nodes[0]
    while True:
        node_id = cast(str, current["id"])
        if node_id in visited:
            raise KernelExecutionError("unsupported_graph_shape")
        visited.add(node_id)
        path.append(current)
        following = next_by_id[node_id]
        if not following:
            break
        if len(following) != 1:
            raise KernelExecutionError("unsupported_graph_shape")
        current = by_id[following[0]]

    kinds = tuple(cast(str, node["kind"]) for node in path)
    if kinds != SUPPORTED_PATH or len(visited) != len(nodes):
        raise KernelExecutionError("unsupported_graph_shape")
    return path


def _find_by_id(
    values: list[dict[str, Any]],
    identifier: str,
    *,
    error_code: str,
) -> dict[str, Any]:
    match = next((value for value in values if value.get("id") == identifier), None)
    if match is None:
        raise KernelExecutionError(error_code)
    return match


def _redacted_mapping(
    value: Mapping[str, object],
    ports: ExecutionPorts,
) -> Mapping[str, object]:
    return cast(
        Mapping[str, object],
        ports.redaction_policy.redact(dict(value)),
    )


class AgentKernel:
    async def execute(
        self,
        command: ExecutionCommand,
        ports: ExecutionPorts,
    ) -> RunOutcome:
        agent = cast(dict[str, Any], dict(command.agent_spec))
        if not validate_agent_spec(agent).valid:
            raise KernelExecutionError("agent_spec_invalid")

        input_node, model_node, tool_node, output_node = _execution_path(agent)
        profiles = cast(list[dict[str, Any]], agent["model_profiles"])
        tools = cast(list[dict[str, Any]], agent["tools"])

        profile_id = cast(str, model_node["model_profile_ref"])
        profile = _find_by_id(
            profiles,
            profile_id,
            error_code="model_profile_not_found",
        )
        routes = cast(list[dict[str, Any]], profile["routes"])
        route = routes[0]

        recorder = EventRecorder(command, ports)
        started_at = ports.clock.now()
        await recorder.emit(
            "run.started",
            {"agent_version_id": command.agent_version_id},
            occurred_at=started_at,
        )

        input_completed_at = ports.clock.now()
        input_value = dict(command.input)
        node_executions: list[NodeExecution] = [
            NodeExecution(
                node_id=cast(str, input_node["id"]),
                status="completed",
                started_at=started_at,
                completed_at=input_completed_at,
                duration_ms=_duration_ms(started_at, input_completed_at),
                input=_redacted_mapping(input_value, ports),
                output=_redacted_mapping(input_value, ports),
            )
        ]

        model_started_at = ports.clock.now()
        await recorder.emit(
            "node.started",
            {},
            node_id=cast(str, model_node["id"]),
            occurred_at=model_started_at,
        )
        await recorder.emit(
            "model.requested",
            {"profile_id": profile_id},
            node_id=cast(str, model_node["id"]),
        )
        tool_request = await ports.model_gateway.complete(
            ModelRequest(
                profile_id=profile_id,
                model=cast(str, route["model"]),
                input=input_value,
                locale=command.locale,
            )
        )
        await recorder.emit(
            "model.completed",
            tool_request.arguments,
            node_id=cast(str, model_node["id"]),
        )
        model_completed_at = ports.clock.now()
        node_executions.append(
            NodeExecution(
                node_id=cast(str, model_node["id"]),
                status="completed",
                started_at=model_started_at,
                completed_at=model_completed_at,
                duration_ms=_duration_ms(model_started_at, model_completed_at),
                input=_redacted_mapping(input_value, ports),
                output=_redacted_mapping(tool_request.arguments, ports),
            )
        )

        configured_tool_id = cast(str, tool_node["tool_ref"])
        if tool_request.tool_id != configured_tool_id:
            raise KernelExecutionError(
                "model_requested_unconfigured_tool",
                node_id=cast(str, model_node["id"]),
            )
        tool_manifest = _find_by_id(
            tools,
            tool_request.tool_id,
            error_code="tool_manifest_not_found",
        )
        _validate_schema(
            tool_request.arguments,
            cast(Mapping[str, object], tool_manifest["input_schema"]),
            code="tool_input_schema_validation_failed",
            node_id=cast(str, tool_node["id"]),
        )

        tool_started_at = ports.clock.now()
        await recorder.emit(
            "tool.requested",
            {"tool_id": tool_request.tool_id},
            node_id=cast(str, tool_node["id"]),
            occurred_at=tool_started_at,
        )
        tool_output = await ports.tool_gateway.invoke(
            tool_request.tool_id,
            tool_request.arguments,
        )
        _validate_schema(
            tool_output,
            cast(Mapping[str, object], tool_manifest["output_schema"]),
            code="tool_output_schema_validation_failed",
            node_id=cast(str, tool_node["id"]),
        )
        tool_completed_event = await recorder.emit(
            "tool.completed",
            tool_output,
            node_id=cast(str, tool_node["id"]),
        )
        node_executions.append(
            NodeExecution(
                node_id=cast(str, tool_node["id"]),
                status="completed",
                started_at=tool_started_at,
                completed_at=tool_completed_event.occurred_at,
                duration_ms=_duration_ms(
                    tool_started_at,
                    tool_completed_event.occurred_at,
                ),
                input=_redacted_mapping(tool_request.arguments, ports),
                output=_redacted_mapping(tool_output, ports),
            )
        )

        _validate_schema(
            tool_output,
            cast(
                Mapping[str, object],
                cast(dict[str, Any], agent["interface"])["result_schema"],
            ),
            code="output_schema_validation_failed",
            node_id=cast(str, output_node["id"]),
        )
        output_started_at = ports.clock.now()
        output_completed_event = await recorder.emit(
            "node.completed",
            tool_output,
            node_id=cast(str, output_node["id"]),
            occurred_at=output_started_at,
        )
        node_executions.append(
            NodeExecution(
                node_id=cast(str, output_node["id"]),
                status="completed",
                started_at=output_started_at,
                completed_at=output_completed_event.occurred_at,
                duration_ms=0,
                input=_redacted_mapping(tool_output, ports),
                output=_redacted_mapping(tool_output, ports),
            )
        )

        completed_event = await recorder.emit(
            "run.completed",
            {"status": "completed"},
        )
        redacted_output = _redacted_mapping(tool_output, ports)
        trace = RunTrace(
            run_id=command.run_id,
            request_id=command.request_id,
            agent_version_id=command.agent_version_id,
            agent_version_digest=command.agent_version_digest,
            status="completed",
            started_at=started_at,
            completed_at=completed_event.occurred_at,
            input=_redacted_mapping(command.input, ports),
            output=redacted_output,
            events=recorder.events,
            node_executions=tuple(node_executions),
            provenance={
                "model_resolutions": [
                    {
                        "profile_id": profile_id,
                        "adapter": cast(str, route["adapter"]),
                        "model": cast(str, route["model"]),
                        "parameters": cast(dict[str, Any], profile["parameters"]),
                        "prompt_digest": content_digest(model_node["config"]),
                    }
                ],
                "tool_resolutions": [
                    {
                        "tool_id": tool_request.tool_id,
                        "version": cast(str, tool_manifest["version"]),
                        "digest": content_digest(tool_manifest),
                    }
                ],
                "redaction_policy_id": ports.redaction_policy.policy_id,
            },
            metrics={
                "duration_ms": _duration_ms(
                    started_at,
                    completed_event.occurred_at,
                ),
                "input_tokens": 0,
                "output_tokens": 0,
                "tool_calls": 1,
                "cost": {"amount": 0, "currency": "USD"},
            },
        )
        await ports.trace_store.save(trace)
        return RunOutcome(output=redacted_output, trace=trace)
