from __future__ import annotations

import dataclasses

import pytest
from universal_agent_kernel.domain import ExecutionCommand, ModelRequest
from universal_agent_kernel.models.fake import FakeModelGateway


@pytest.mark.asyncio
async def test_fake_model_returns_the_locked_calculator_request() -> None:
    gateway = FakeModelGateway()
    request = ModelRequest(
        profile_id="deterministic-planner",
        model="calculator-planner-v1",
        input={"question": "Сколько будет 19 × 23?"},
        locale="ru-RU",
    )

    first = await gateway.complete(request)
    second = await gateway.complete(request)

    assert first == second
    assert first.tool_id == "builtin-calculator"
    assert first.arguments == {
        "operation": "multiply",
        "left": 19,
        "right": 23,
    }


def test_domain_command_has_no_provider_specific_fields() -> None:
    field_names = {
        field.name
        for field in dataclasses.fields(ExecutionCommand)
    }

    assert not field_names & {"openai", "anthropic", "provider", "api_key"}
