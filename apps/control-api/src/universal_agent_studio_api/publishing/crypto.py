"""Separated cryptographic material for public credentials."""

from __future__ import annotations

import base64
import hashlib
import hmac
import secrets
from dataclasses import dataclass
from pathlib import Path
from uuid import UUID


def _require_master_key(master_key: bytes) -> bytes:
    value = master_key.strip()
    if len(value) < 32:
        raise ValueError("publishing_master_key_too_short")
    return value


def load_master_key(path: Path) -> bytes:
    return _require_master_key(path.read_bytes())


def _base64url(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


@dataclass(frozen=True)
class IssuedApiKey:
    raw: str
    prefix: str
    key_hash: str


def api_key_hash(master_key: bytes, raw_key: str) -> str:
    return hmac.new(
        _require_master_key(master_key),
        raw_key.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()


def issue_api_key(master_key: bytes) -> IssuedApiKey:
    prefix = secrets.token_hex(8)
    raw = f"uas_live_{prefix}_{_base64url(secrets.token_bytes(32))}"
    return IssuedApiKey(
        raw=raw,
        prefix=prefix,
        key_hash=api_key_hash(master_key, raw),
    )


def verify_api_key_hash(
    master_key: bytes,
    raw_key: str,
    expected_hash: str,
) -> bool:
    return hmac.compare_digest(
        api_key_hash(master_key, raw_key),
        expected_hash,
    )


def derive_webhook_secret(master_key: bytes, key_id: UUID) -> str:
    derived = hmac.new(
        _require_master_key(master_key),
        b"uas:webhook:v1:" + key_id.bytes,
        hashlib.sha256,
    ).digest()
    return f"whsec_{_base64url(derived)}"
