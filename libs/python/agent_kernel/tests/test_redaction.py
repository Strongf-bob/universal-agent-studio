from universal_agent_kernel.redaction.policy import DefaultRedactionPolicy


def test_redaction_recurses_through_secret_aliases() -> None:
    value = {
        "safe": "visible",
        "api_key": "top-secret",
        "nested": [
            {"Authorization": "Bearer secret"},
            {"clientSecret": "another-secret", "count": 2},
        ],
    }

    redacted = DefaultRedactionPolicy().redact(value)

    assert redacted == {
        "safe": "visible",
        "api_key": "[REDACTED]",
        "nested": [
            {"Authorization": "[REDACTED]"},
            {"clientSecret": "[REDACTED]", "count": 2},
        ],
    }
    assert value["api_key"] == "top-secret"
