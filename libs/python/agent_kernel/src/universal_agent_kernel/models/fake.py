"""Deterministic model gateway used by local development and CI."""

from universal_agent_kernel.domain import (
    ModelExecutionError,
    ModelRequest,
    ToolRequest,
)


class FakeModelGateway:
    async def complete(self, request: ModelRequest) -> ToolRequest:
        if (
            request.profile_id != "deterministic-planner"
            or request.model != "calculator-planner-v1"
        ):
            raise ModelExecutionError("fake_model_route_not_supported")
        return ToolRequest(
            tool_id="builtin-calculator",
            arguments={
                "operation": "multiply",
                "left": 19,
                "right": 23,
            },
        )
