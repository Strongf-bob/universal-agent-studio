from __future__ import annotations

from universal_agent_studio_runtime.webhooks.signing import sign_webhook


def test_webhook_signature_matches_fixed_vector() -> None:
    body = (
        b'{"delivery_id":"00000000-0000-0000-0000-000000000001"}'
    )

    signature = sign_webhook(b"k" * 32, 1_753_392_000, body)

    assert (
        signature
        == "v1=bdfe974410085c58ae53d60ff47fffed1bc06887ada3edc020e1a21af8c419b5"
    )
