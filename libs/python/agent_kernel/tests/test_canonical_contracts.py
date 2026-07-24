from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any, cast

import pytest
from universal_agent_kernel.contracts.canonical import (
    CanonicalJsonError,
    content_digest,
    parse_json_document,
)
from universal_agent_kernel.contracts.validation import validate_agent_spec

ROOT = Path(__file__).parents[4]
GOLDEN_AGENT = (
    ROOT
    / "contracts"
    / "examples"
    / "v0.1.0"
    / "valid"
    / "agent.calculator.ru-en.json"
)
GOLDEN_DIGEST = (
    ROOT / "tests" / "fixtures" / "canonical" / "agent.calculator.sha256"
)


def load_golden_agent() -> dict[str, Any]:
    return cast(dict[str, Any], json.loads(GOLDEN_AGENT.read_text(encoding="utf-8")))


def test_object_key_order_does_not_change_digest() -> None:
    first = {"alpha": 1, "nested": {"beta": True, "gamma": None}}
    second = {"nested": {"gamma": None, "beta": True}, "alpha": 1}

    assert content_digest(first) == content_digest(second)


def test_numeric_spelling_has_rfc8785_digest() -> None:
    integer_spelling = parse_json_document('{"value": 1}')
    decimal_spelling = parse_json_document('{"value": 1.0}')

    assert content_digest(integer_spelling) == content_digest(decimal_spelling)


def test_golden_agent_digest_matches_locked_vector() -> None:
    expected = GOLDEN_DIGEST.read_text(encoding="utf-8").strip()

    assert len(expected) == 64
    assert content_digest(load_golden_agent()) == expected


def test_duplicate_json_key_is_rejected_before_hashing() -> None:
    with pytest.raises(CanonicalJsonError) as error:
        parse_json_document('{"agent_id": "first", "agent_id": "second"}')

    assert error.value.code == "duplicate_json_key"
    assert error.value.key == "agent_id"


def test_invalid_agent_reports_json_pointer_and_node_id() -> None:
    invalid_agent = copy.deepcopy(load_golden_agent())
    invalid_agent["nodes"][2]["timeout_ms"] = 0

    result = validate_agent_spec(invalid_agent)

    assert result.valid is False
    assert any(
        issue.code == "schema_validation_failed"
        and issue.json_pointer == "/nodes/2/timeout_ms"
        and issue.node_id == "calculator-tool"
        for issue in result.issues
    )
