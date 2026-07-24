"""RFC 8785 canonical JSON parsing and hashing."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable
from typing import Any

import rfc8785


class CanonicalJsonError(ValueError):
    """A stable, non-secret-bearing canonical JSON error."""

    def __init__(self, code: str, *, key: str | None = None) -> None:
        self.code = code
        self.key = key
        super().__init__(code)


def _reject_duplicate_keys(pairs: Iterable[tuple[str, Any]]) -> dict[str, Any]:
    document: dict[str, Any] = {}
    for key, value in pairs:
        if key in document:
            raise CanonicalJsonError("duplicate_json_key", key=key)
        document[key] = value
    return document


def parse_json_document(raw: str | bytes | bytearray) -> Any:
    """Parse JSON while rejecting duplicate object keys before canonicalization."""

    try:
        return json.loads(raw, object_pairs_hook=_reject_duplicate_keys)
    except CanonicalJsonError:
        raise
    except (json.JSONDecodeError, UnicodeDecodeError) as error:
        raise CanonicalJsonError("invalid_json") from error


def canonicalize(document: Any) -> bytes:
    """Return RFC 8785 JSON Canonicalization Scheme bytes."""

    try:
        return rfc8785.dumps(document)
    except (rfc8785.CanonicalizationError, TypeError, ValueError) as error:
        raise CanonicalJsonError("json_not_canonicalizable") from error


def content_digest(document: Any) -> str:
    """Return a lowercase SHA-256 digest of canonical JSON bytes."""

    return hashlib.sha256(canonicalize(document)).hexdigest()
