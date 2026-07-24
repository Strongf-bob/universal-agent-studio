from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

from universal_agent_kernel.contracts.validation import validation_codes


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


def validate_fixture(case: ContractCase, root: Path) -> list[str]:
    instance = load_json(
        root / "contracts" / "examples" / "v0.1.0" / case.path
    )
    return validation_codes(instance, case.schema)
