"""Shared deterministic webhook secret derivation."""

from __future__ import annotations

import base64
import hashlib
import hmac
from uuid import UUID


def derive_webhook_secret(master_key: bytes, key_id: UUID) -> str:
    key = master_key.strip()
    if len(key) < 32:
        raise ValueError("publishing_master_key_too_short")
    derived = hmac.new(
        key,
        b"uas:webhook:v1:" + key_id.bytes,
        hashlib.sha256,
    ).digest()
    encoded = base64.urlsafe_b64encode(derived).rstrip(b"=").decode("ascii")
    return f"whsec_{encoded}"
