from __future__ import annotations

import copy
import os
import secrets
import shutil
import subprocess
from pathlib import Path

import httpx
import pytest

ROOT = Path(__file__).parents[2]
COMPOSE = ROOT / "infra" / "docker" / "compose.local.yml"
SECRETS = ROOT / ".local" / "secrets"
BASE_URL = os.getenv("UAS_E2E_BASE_URL", "http://localhost:3000")


def _docker_compose(*arguments: str) -> str:
    if shutil.which("docker") is None:
        pytest.skip("Docker is unavailable")
    completed = subprocess.run(
        ["docker", "compose", "-f", str(COMPOSE), *arguments],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    return completed.stdout + completed.stderr


def test_generated_secrets_are_absent_from_compose_logs_and_browser_bundle() -> None:
    secret_files = sorted(SECRETS.glob("*"))
    if not secret_files:
        pytest.skip("Local stack secrets have not been generated")
    secret_values = [path.read_text(encoding="utf-8").strip() for path in secret_files]
    assert all(len(value) >= 32 for value in secret_values)

    observed = _docker_compose("config") + _docker_compose("logs", "--no-color")
    static_root = ROOT / "apps" / "studio-web" / ".next" / "static"
    if static_root.exists():
        observed += "".join(
            path.read_text(encoding="utf-8", errors="ignore")
            for path in static_root.rglob("*")
            if path.is_file()
        )

    for secret in secret_values:
        assert secret not in observed


def test_rejected_draft_secret_is_absent_from_api_database_and_trace() -> None:
    try:
        bootstrap = httpx.get(
            f"{BASE_URL}/api/v1/bootstrap/status",
            timeout=1,
        )
    except httpx.HTTPError:
        pytest.skip("The complete local stack is not running")
    if not bootstrap.is_success:
        pytest.skip("The complete local stack is not ready")

    forbidden = f"slice2-secret-{secrets.token_urlsafe(32)}"
    with httpx.Client(
        base_url=BASE_URL,
        headers={"Origin": BASE_URL},
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
        current = client.get("/api/v1/agents/calculator-agent/draft")
        assert current.status_code == 200
        candidate = copy.deepcopy(current.json()["agent_spec"])
        candidate["nodes"][0]["config"]["api_key"] = forbidden
        response = client.post(
            "/api/v1/agents/calculator-agent/draft/diff",
            headers={"X-CSRF-Token": csrf_token},
            json={
                "expected_revision": current.json()["revision"],
                "candidate_agent_spec": candidate,
            },
        )

        assert response.status_code == 422
        assert response.json()["code"] == "agent_spec_invalid"
        assert forbidden not in response.text
        persisted = client.get("/api/v1/agents/calculator-agent/draft")
        assert persisted.status_code == 200
        assert forbidden not in persisted.text

    database_documents = _docker_compose(
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
            "SELECT COALESCE(string_agg(document, E'\\n'), '') "
            "FROM ("
            "SELECT agent_spec::text AS document FROM agent_drafts "
            "UNION ALL "
            "SELECT document::text AS document FROM run_traces"
            ") AS persisted_documents"
        ),
    )
    assert forbidden not in database_documents
