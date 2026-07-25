from __future__ import annotations

import os
import secrets

import httpx
import pytest

from tests.security.test_secret_absence import _docker_compose

STUDIO_URL = os.getenv("UAS_E2E_BASE_URL", "http://localhost:3000")
PUBLISHED_URL = os.getenv(
    "UAS_E2E_PUBLISHED_BASE_URL",
    "http://127.0.0.1:3301",
)


def test_issued_slice3_secrets_never_reach_storage_logs_or_public_html() -> None:
    try:
        health = httpx.get(
            f"{STUDIO_URL}/api/v1/bootstrap/status",
            timeout=2,
        )
    except httpx.HTTPError:
        pytest.skip("The complete local stack is not running")
    if not health.is_success:
        pytest.skip("The complete local stack is not ready")

    marker = secrets.token_hex(8)
    with httpx.Client(
        base_url=STUDIO_URL,
        headers={"Origin": STUDIO_URL},
        timeout=10,
    ) as client:
        login = client.post(
            "/api/v1/session",
            json={
                "login_name": "slice1-owner",
                "password": "slice1-e2e-secret-437",
            },
        )
        assert login.status_code == 201
        csrf_token = login.json()["csrf_token"]
        created_key = client.post(
            "/api/v1/agents/calculator-agent/api-keys",
            headers={"X-CSRF-Token": csrf_token},
            json={
                "label": f"secret-scan-{marker}",
                "scopes": ["runs:create", "runs:read", "events:read"],
                "expires_at": None,
            },
        )
        assert created_key.status_code == 201
        key_document = created_key.json()
        raw_key = key_document["secret"]
        assert raw_key.startswith("uas_live_")

        created_webhook = client.post(
            "/api/v1/agents/calculator-agent/webhooks",
            headers={"X-CSRF-Token": csrf_token},
            json={
                "label": f"secret-scan-{marker}",
                "target_url": "https://hooks.example.test/secret-scan",
                "events": ["run.completed"],
            },
        )
        assert created_webhook.status_code == 201
        webhook_document = created_webhook.json()
        raw_webhook_secret = webhook_document["secret"]
        assert raw_webhook_secret.startswith("whsec_")

        for endpoint in (
            (
                "/api/v1/agents/calculator-agent/api-keys/"
                f"{key_document['key_id']}/revoke"
            ),
            (
                "/api/v1/agents/calculator-agent/webhooks/"
                f"{webhook_document['subscription_id']}/revoke"
            ),
        ):
            revoked = client.post(
                endpoint,
                headers={"X-CSRF-Token": csrf_token},
            )
            assert revoked.status_code == 200
            assert raw_key not in revoked.text
            assert raw_webhook_secret not in revoked.text

    persisted = _docker_compose(
        "exec",
        "-T",
        "postgres",
        "psql",
        "-U",
        "uas",
        "-d",
        "uas",
        "-At",
        "-c",
        (
            "SELECT COALESCE(string_agg(document, E'\\n'), '') FROM ("
            "SELECT key_hash AS document FROM agent_api_keys "
            "UNION ALL SELECT signing_key_id::text FROM webhook_subscriptions "
            "UNION ALL SELECT payload::text FROM webhook_deliveries "
            "UNION ALL SELECT document::text FROM run_traces"
            ") AS secret_scan"
        ),
    )
    logs = _docker_compose("logs", "--no-color")
    public_html = httpx.get(
        f"{PUBLISHED_URL}/en-US/agents/calculator-agent",
        timeout=10,
    ).text

    for raw_secret in (raw_key, raw_webhook_secret):
        assert raw_secret not in persisted
        assert raw_secret not in logs
        assert raw_secret not in public_html
