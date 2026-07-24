"""Signed, provider-neutral execution commands shared by API and worker."""

from __future__ import annotations

import hashlib
import hmac
from collections.abc import Mapping
from typing import Any, cast
from uuid import UUID

from universal_agent_kernel.contracts.canonical import canonicalize
from universal_agent_kernel.domain import ExecutionCommand

MINIMUM_SIGNING_KEY_BYTES = 32


def execution_command_to_document(
    command: ExecutionCommand,
) -> dict[str, Any]:
    return {
        "run_id": str(command.run_id),
        "request_id": str(command.request_id),
        "workspace_id": str(command.workspace_id),
        "project_id": str(command.project_id),
        "agent_version_id": command.agent_version_id,
        "agent_version_digest": command.agent_version_digest,
        "agent_spec": dict(command.agent_spec),
        "input": dict(command.input),
        "locale": command.locale,
    }


def execution_command_from_document(
    document: Mapping[str, Any],
) -> ExecutionCommand:
    try:
        return ExecutionCommand(
            run_id=UUID(str(document["run_id"])),
            request_id=UUID(str(document["request_id"])),
            workspace_id=UUID(str(document["workspace_id"])),
            project_id=UUID(str(document["project_id"])),
            agent_version_id=str(document["agent_version_id"]),
            agent_version_digest=str(document["agent_version_digest"]),
            agent_spec=cast(Mapping[str, object], document["agent_spec"]),
            input=cast(Mapping[str, object], document["input"]),
            locale=str(document["locale"]),
        )
    except (KeyError, TypeError, ValueError) as error:
        raise ValueError("execution_command_invalid") from error


def _validated_key(signing_key: bytes) -> bytes:
    if len(signing_key) < MINIMUM_SIGNING_KEY_BYTES:
        raise ValueError("execution_signing_key_too_short")
    return signing_key


def sign_execution_command(
    command: ExecutionCommand,
    signing_key: bytes,
) -> dict[str, Any]:
    payload = execution_command_to_document(command)
    signature = hmac.new(
        _validated_key(signing_key),
        canonicalize(payload),
        hashlib.sha256,
    ).hexdigest()
    return {"payload": payload, "signature": signature}


def verify_execution_envelope(
    envelope: Mapping[str, Any],
    signing_key: bytes,
) -> ExecutionCommand:
    payload = envelope.get("payload")
    signature = envelope.get("signature")
    if not isinstance(payload, dict) or not isinstance(signature, str):
        raise ValueError("execution_envelope_invalid")
    expected = hmac.new(
        _validated_key(signing_key),
        canonicalize(payload),
        hashlib.sha256,
    ).hexdigest()
    if len(signature) != 64 or not hmac.compare_digest(signature, expected):
        raise ValueError("execution_envelope_invalid")
    return execution_command_from_document(payload)
