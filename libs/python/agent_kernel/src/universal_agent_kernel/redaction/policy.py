"""Recursive redaction of credential-shaped object keys."""

from __future__ import annotations

import re
from typing import Any

from universal_agent_kernel.contracts.validation import FORBIDDEN_SECRET_KEYS

REDACTED = "[REDACTED]"


def _normalized_key(key: object) -> str:
    snake_key = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", str(key))
    return re.sub(r"[^a-z0-9]", "", snake_key.lower())


class DefaultRedactionPolicy:
    policy_id = "default-redaction"

    def redact(self, value: Any) -> Any:
        if isinstance(value, dict):
            return {
                key: (
                    REDACTED
                    if _normalized_key(key) in FORBIDDEN_SECRET_KEYS
                    else self.redact(child)
                )
                for key, child in value.items()
            }
        if isinstance(value, list):
            return [self.redact(child) for child in value]
        return value
