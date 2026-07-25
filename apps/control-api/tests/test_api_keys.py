from __future__ import annotations

from universal_agent_studio_api.publishing.crypto import (
    issue_api_key,
    verify_api_key_hash,
)


def test_api_key_is_one_time_material_with_keyed_hash() -> None:
    issued = issue_api_key(b"h" * 32)

    assert issued.raw.startswith(f"uas_live_{issued.prefix}_")
    assert len(issued.prefix) == 16
    assert len(issued.key_hash) == 64
    assert issued.raw not in issued.key_hash
    assert verify_api_key_hash(b"h" * 32, issued.raw, issued.key_hash)
    assert not verify_api_key_hash(b"x" * 32, issued.raw, issued.key_hash)


def test_api_key_hash_changes_with_raw_key() -> None:
    first = issue_api_key(b"h" * 32)
    second = issue_api_key(b"h" * 32)

    assert first.raw != second.raw
    assert first.key_hash != second.key_hash
