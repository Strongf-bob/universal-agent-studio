"""Canonical webhook HMAC signatures."""

from __future__ import annotations

import hashlib
import hmac


def sign_webhook(secret: bytes, timestamp: int, body: bytes) -> str:
    digest = hmac.new(
        secret,
        str(timestamp).encode("ascii") + b"." + body,
        hashlib.sha256,
    ).hexdigest()
    return f"v1={digest}"
