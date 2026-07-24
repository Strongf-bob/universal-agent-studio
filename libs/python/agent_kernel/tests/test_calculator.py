from __future__ import annotations

import math

import pytest
from universal_agent_kernel.domain import ToolExecutionError
from universal_agent_kernel.tools.calculator import CalculatorTool


@pytest.mark.asyncio
async def test_calculator_multiplies_without_expression_evaluation() -> None:
    result = await CalculatorTool().invoke(
        "builtin-calculator",
        {"operation": "multiply", "left": 19, "right": 23},
    )

    assert result == {"value": 437}


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("arguments", "code"),
    [
        ({"operation": "power", "left": 2, "right": 8}, "unsupported_operation"),
        (
            {"operation": "add", "left": math.inf, "right": 1},
            "non_finite_number",
        ),
        (
            {"operation": "add", "left": True, "right": 1},
            "invalid_number",
        ),
        (
            {"operation": "divide", "left": 1, "right": 0},
            "division_by_zero",
        ),
    ],
)
async def test_calculator_rejects_unsafe_inputs(
    arguments: dict[str, object],
    code: str,
) -> None:
    with pytest.raises(ToolExecutionError) as error:
        await CalculatorTool().invoke("builtin-calculator", arguments)

    assert error.value.code == code
