"""Stable PostgreSQL advisory-lock identities shared across repositories."""

from __future__ import annotations

from uuid import UUID


def agent_publication_lock_key(
    workspace_id: UUID,
    project_id: UUID,
    agent_key: str,
) -> str:
    return f"{workspace_id}:{project_id}:{agent_key}:publish"


def public_agent_key_lock_key(agent_key: str) -> str:
    return f"public-agent-key:{agent_key}"
