"""A finite, side-effect-free arithmetic tool."""

from __future__ import annotations

import math
import operator
from collections.abc import Callable, Mapping

from universal_agent_kernel.domain import ToolExecutionError

Number = int | float
OPERATIONS: dict[str, Callable[[Number, Number], Number]] = {
    "add": operator.add,
    "subtract": operator.sub,
    "multiply": operator.mul,
    "divide": operator.truediv,
}


def _number(value: object) -> Number:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ToolExecutionError("invalid_number")
    if not math.isfinite(value):
        raise ToolExecutionError("non_finite_number")
    return value


class CalculatorTool:
    async def invoke(
        self,
        tool_id: str,
        arguments: Mapping[str, object],
    ) -> Mapping[str, object]:
        if tool_id != "builtin-calculator":
            raise ToolExecutionError("tool_not_supported")

        operation = arguments.get("operation")
        if not isinstance(operation, str) or operation not in OPERATIONS:
            raise ToolExecutionError("unsupported_operation")
        left = _number(arguments.get("left"))
        right = _number(arguments.get("right"))
        if operation == "divide" and right == 0:
            raise ToolExecutionError("division_by_zero")

        result = OPERATIONS[operation](left, right)
        if not math.isfinite(result):
            raise ToolExecutionError("non_finite_result")
        return {"value": result}
