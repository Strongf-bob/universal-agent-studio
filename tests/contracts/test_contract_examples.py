import json
from pathlib import Path

import pytest

from tests.contracts.contract_validation import ContractCase, validate_fixture

ROOT = Path(__file__).parents[2]
EXAMPLE_DIR = ROOT / "contracts" / "examples" / "v0.1.0"
MANIFEST = json.loads((EXAMPLE_DIR / "manifest.json").read_text(encoding="utf-8"))


@pytest.mark.parametrize(
    "case",
    [ContractCase.from_dict(value) for value in MANIFEST["cases"]],
    ids=[value["path"] for value in MANIFEST["cases"]],
)
def test_fixture_matches_declared_validity(case: ContractCase) -> None:
    errors = validate_fixture(case, ROOT)

    if case.valid:
        assert errors == []
    else:
        assert case.expected_error_code in errors


def test_valid_trace_has_contiguous_event_sequence() -> None:
    trace = json.loads(
        (EXAMPLE_DIR / "valid" / "run.trace.completed.json").read_text(
            encoding="utf-8"
        )
    )

    assert [event["sequence"] for event in trace["events"]] == list(
        range(1, len(trace["events"]) + 1)
    )
