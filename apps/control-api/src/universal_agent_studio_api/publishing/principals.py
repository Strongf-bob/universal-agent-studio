"""Least-privilege public API and run-capability principals."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID

from universal_agent_studio_api.publishing.crypto import _require_master_key


def _encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def _decode(value: str) -> bytes:
    padding = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode(value + padding)


@dataclass(frozen=True)
class PublicPrincipal:
    kind: str
    workspace_id: UUID
    project_id: UUID
    agent_id: str
    scopes: frozenset[str]
    key_id: UUID | None = None
    run_id: UUID | None = None


def issue_run_capability(
    master_key: bytes,
    *,
    workspace_id: UUID,
    project_id: UUID,
    agent_id: str,
    run_id: UUID,
    expires_at: datetime,
) -> str:
    if expires_at.tzinfo is None:
        raise ValueError("run_capability_invalid")
    payload = json.dumps(
        {
            "v": 1,
            "w": str(workspace_id),
            "p": str(project_id),
            "a": agent_id,
            "r": str(run_id),
            "exp": int(expires_at.timestamp()),
        },
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    signature = hmac.new(
        _require_master_key(master_key),
        b"uas:run-capability:v1:" + payload,
        hashlib.sha256,
    ).digest()
    return f"uascap_{_encode(payload)}.{_encode(signature)}"


def verify_run_capability(
    master_key: bytes,
    raw: str,
    *,
    agent_id: str,
    run_id: UUID,
    now: datetime | None = None,
) -> PublicPrincipal:
    try:
        prefix, separator, raw_signature = raw.partition(".")
        if not separator or not prefix.startswith("uascap_"):
            raise ValueError
        payload = _decode(prefix.removeprefix("uascap_"))
        signature = _decode(raw_signature)
        expected = hmac.new(
            _require_master_key(master_key),
            b"uas:run-capability:v1:" + payload,
            hashlib.sha256,
        ).digest()
        if not hmac.compare_digest(signature, expected):
            raise ValueError
        document = json.loads(payload)
        if not isinstance(document, dict) or document.get("v") != 1:
            raise ValueError
        token_agent = str(document["a"])
        token_run = UUID(str(document["r"]))
        expires_at = int(document["exp"])
        current = now or datetime.now(UTC)
        if (
            token_agent != agent_id
            or token_run != run_id
            or int(current.timestamp()) >= expires_at
        ):
            raise ValueError
        return PublicPrincipal(
            kind="run_capability",
            workspace_id=UUID(str(document["w"])),
            project_id=UUID(str(document["p"])),
            agent_id=token_agent,
            run_id=token_run,
            scopes=frozenset({"runs:read", "events:read"}),
        )
    except (KeyError, TypeError, ValueError, json.JSONDecodeError) as error:
        raise ValueError("run_capability_invalid") from error
