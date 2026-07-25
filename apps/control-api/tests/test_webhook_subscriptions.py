from __future__ import annotations

from uuid import UUID

import pytest
from universal_agent_studio_api.publishing.crypto import derive_webhook_secret
from universal_agent_studio_api.publishing.service import validate_webhook_target


def test_webhook_secret_is_stable_and_domain_separated() -> None:
    subscription_id = UUID("11111111-1111-4111-8111-111111111111")

    first = derive_webhook_secret(b"w" * 32, subscription_id)
    second = derive_webhook_secret(b"w" * 32, subscription_id)

    assert first == second
    assert first.startswith("whsec_")
    assert len(first) == 49
    assert first != derive_webhook_secret(b"k" * 32, subscription_id)


@pytest.mark.parametrize(
    "target",
    [
        "http://user@example.test/hook",
        "http://example.test/hook#fragment",
        "ftp://example.test/hook",
        "http://127.0.0.1:9090/hook",
    ],
)
def test_webhook_target_rejects_unsafe_or_unlisted_urls(target: str) -> None:
    with pytest.raises(ValueError, match="webhook_origin_not_allowed"):
        validate_webhook_target(
            target,
            allowed_origins=["http://example.test"],
        )


def test_webhook_target_accepts_exact_origin() -> None:
    assert (
        validate_webhook_target(
            "http://example.test:9090/hooks/completed",
            allowed_origins=["http://example.test:9090"],
        )
        == "http://example.test:9090/hooks/completed"
    )
